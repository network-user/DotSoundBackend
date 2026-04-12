from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from fastapi import WebSocket
from redis.asyncio import Redis

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


_PRESENCE_TTL = 120
_PRESENCE_PREFIX = "presence:"

ACTIVITY_TYPES = frozenset(
    {
        "typing",
        "recording_audio",
        "sending_photo",
        "idle",
    }
)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[
            int, list[WebSocket]
        ] = {}
        self._redis: Redis | None = None  # type: ignore[type-arg]
        self._pubsub_task: asyncio.Task[None] | None = (
            None
        )
        self._heartbeat_task: asyncio.Task[None] | None = (
            None
        )

    async def startup(self) -> None:
        self._redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._pubsub_task = asyncio.create_task(
            self._listen_redis()
        )
        self._heartbeat_task = asyncio.create_task(
            self._presence_heartbeat()
        )
        logger.info("ws_manager_started")

    async def shutdown(self) -> None:
        for task in (
            self._pubsub_task,
            self._heartbeat_task,
        ):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if self._redis:
            for uid in list(self._connections):
                await self._redis.delete(
                    f"{_PRESENCE_PREFIX}{uid}"
                )
            await self._redis.aclose()
        logger.info("ws_manager_stopped")

    async def connect(
        self, user_id: int, ws: WebSocket
    ) -> None:
        await ws.accept()
        self._connections.setdefault(
            user_id, []
        ).append(ws)
        if self._redis:
            await self._redis.subscribe(
                f"user:{user_id}"
            )
            await self._set_presence(
                user_id, "online"
            )
        logger.debug(
            "ws_connected", user_id=user_id
        )

    async def disconnect(
        self, user_id: int, ws: WebSocket
    ) -> None:
        conns = self._connections.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(user_id, None)
            if self._redis:
                await self._redis.unsubscribe(
                    f"user:{user_id}"
                )
                await self._set_presence(
                    user_id, "offline"
                )
        logger.debug(
            "ws_disconnected", user_id=user_id
        )

    def get_online_user_ids(self) -> set[int]:
        return set(self._connections.keys())

    async def send_to_user(
        self, user_id: int, data: dict[str, Any]
    ) -> None:
        if self._redis:
            await self._redis.publish(
                f"user:{user_id}", json.dumps(data)
            )

    async def send_to_conversation(
        self,
        member_ids: list[int],
        data: dict[str, Any],
    ) -> None:
        for uid in member_ids:
            await self.send_to_user(uid, data)

    async def _set_presence(
        self, user_id: int, status: str
    ) -> None:
        if not self._redis:
            return
        import time

        key = f"{_PRESENCE_PREFIX}{user_id}"
        value = json.dumps(
            {"status": status, "ts": time.time()}
        )
        if status == "offline":
            await self._redis.set(
                key, value, ex=86400 * 7
            )
        else:
            await self._redis.set(
                key, value, ex=_PRESENCE_TTL
            )

    async def get_presence(
        self, user_id: int
    ) -> dict[str, Any]:
        if not self._redis:
            return {"status": "offline", "ts": 0}
        raw = await self._redis.get(
            f"{_PRESENCE_PREFIX}{user_id}"
        )
        if not raw:
            return {"status": "offline", "ts": 0}
        return json.loads(raw)  # type: ignore[no-any-return]

    async def get_presence_bulk(
        self, user_ids: list[int]
    ) -> dict[int, dict[str, Any]]:
        result: dict[int, dict[str, Any]] = {}
        for uid in user_ids:
            result[uid] = await self.get_presence(
                uid
            )
        return result

    async def broadcast_activity(
        self,
        user_id: int,
        conversation_id: int,
        member_ids: list[int],
        activity: str,
    ) -> None:
        event = {
            "event": "activity",
            "user_id": user_id,
            "conversation_id": conversation_id,
            "activity": activity,
        }
        for uid in member_ids:
            if uid != user_id:
                await self.send_to_user(uid, event)

    async def _presence_heartbeat(self) -> None:
        try:
            while True:
                for uid in list(
                    self._connections.keys()
                ):
                    await self._set_presence(
                        uid, "online"
                    )
                await asyncio.sleep(
                    _PRESENCE_TTL // 2
                )
        except asyncio.CancelledError:
            raise

    async def _deliver_local(
        self, user_id: int, data: dict[str, Any]
    ) -> None:
        conns = self._connections.get(
            user_id, []
        ).copy()
        payload = json.dumps(data)
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(user_id, ws)

    async def _listen_redis(self) -> None:
        if not self._redis:
            return
        pubsub = self._redis.pubsub()
        subscribed: set[str] = set()
        try:
            while True:
                desired = {
                    f"user:{uid}"
                    for uid in self._connections
                }
                to_add = desired - subscribed
                to_remove = subscribed - desired
                for ch in to_add:
                    try:
                        await pubsub.subscribe(ch)
                    except Exception:
                        pass
                for ch in to_remove:
                    try:
                        await pubsub.unsubscribe(ch)
                    except Exception:
                        pass
                subscribed = (
                    subscribed | to_add
                ) - to_remove

                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if msg and msg["type"] == "message":
                    ch_name: str = msg["channel"]  # type: ignore[assignment]
                    if isinstance(ch_name, bytes):
                        ch_name = ch_name.decode()
                    if ch_name.startswith("user:"):
                        uid_str = ch_name.split(
                            ":", 1
                        )[1]
                        try:
                            uid = int(uid_str)
                        except ValueError:
                            continue
                        data = json.loads(
                            msg["data"]
                        )
                        await self._deliver_local(
                            uid, data
                        )
                else:
                    await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            await pubsub.aclose()
            raise


ws_manager = ConnectionManager()
