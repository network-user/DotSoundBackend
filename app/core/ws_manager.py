from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from fastapi import WebSocket
from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


_PRESENCE_TTL = 120
_PRESENCE_PREFIX = "presence:"
_MAX_WS_PER_USER = 6

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
        self._pubsub: PubSub | None = None
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
        self._pubsub = self._redis.pubsub()
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
        if self._pubsub:
            await self._pubsub.aclose()
        if self._redis:
            for uid in list(self._connections):
                await self._redis.delete(
                    f"{_PRESENCE_PREFIX}{uid}"
                )
            await self._redis.aclose()
        logger.info("ws_manager_stopped")

    async def connect(
        self,
        user_id: int,
        ws: WebSocket,
        subprotocol: str | None = None,
    ) -> bool:
        existing = self._connections.get(user_id, [])
        if len(existing) >= _MAX_WS_PER_USER:
            logger.warning(
                "ws_per_user_cap_exceeded",
                user_id=user_id,
                cap=_MAX_WS_PER_USER,
            )
            await ws.close(code=4429)
            return False
        if subprotocol:
            await ws.accept(subprotocol=subprotocol)
        else:
            await ws.accept()
        is_first = user_id not in self._connections
        self._connections.setdefault(
            user_id, []
        ).append(ws)
        if is_first and self._pubsub:
            await self._pubsub.subscribe(
                f"user:{user_id}"
            )
        if self._redis:
            await self._set_presence(
                user_id, "online"
            )
        logger.debug(
            "ws_connected", user_id=user_id
        )
        return True

    async def disconnect(
        self, user_id: int, ws: WebSocket
    ) -> None:
        conns = self._connections.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(user_id, None)
            if self._pubsub:
                await self._pubsub.unsubscribe(
                    f"user:{user_id}"
                )
            if self._redis:
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

    async def broadcast_to_online(
        self, data: dict[str, Any]
    ) -> None:
        for uid in list(self._connections.keys()):
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

    async def set_chat_activity(
        self,
        conversation_id: int,
        user_id: int,
        activity: str,
    ) -> None:
        if not self._redis:
            return
        import time

        key = f"activity:{conversation_id}:{user_id}"
        if activity == "idle":
            await self._redis.delete(key)
        else:
            value = json.dumps(
                {
                    "activity": activity,
                    "user_id": user_id,
                    "ts": time.time(),
                }
            )
            await self._redis.set(key, value, ex=8)

    async def get_chat_activity(
        self,
        conversation_id: int,
        exclude_user_id: int,
    ) -> dict[str, Any]:
        if not self._redis:
            return {"activities": []}
        import time

        pattern = f"activity:{conversation_id}:*"
        activities: list[dict[str, Any]] = []
        async for key in self._redis.scan_iter(
            match=pattern
        ):
            raw = await self._redis.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            if data["user_id"] == exclude_user_id:
                continue
            if time.time() - data["ts"] > 8:
                continue
            activities.append(data)
        return {"activities": activities}

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
        if not conns:
            logger.debug(
                "ws_no_local_conns",
                user_id=user_id,
                ws_event=data.get("event"),
            )
            return
        payload = json.dumps(data)
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(user_id, ws)
        logger.debug(
            "ws_delivered",
            user_id=user_id,
            ws_event=data.get("event"),
            count=len(conns) - len(dead),
        )

    def _parse_and_deliver(
        self, msg: dict[str, Any]
    ) -> int | None:
        ch_name: str = msg["channel"]  # type: ignore[assignment]
        if isinstance(ch_name, bytes):
            ch_name = ch_name.decode()
        if not ch_name.startswith("user:"):
            return None
        uid_str = ch_name.split(":", 1)[1]
        try:
            return int(uid_str)
        except ValueError:
            return None

    async def _listen_redis(self) -> None:
        if not self._redis:
            return
        pubsub = self._pubsub
        if not pubsub:
            return
        try:
            while True:
                try:
                    msg = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=0.5,
                    )
                except RuntimeError:
                    await asyncio.sleep(0.5)
                    continue
                if not msg:
                    await asyncio.sleep(0.01)
                    continue

                if msg["type"] != "message":
                    continue

                uid = self._parse_and_deliver(msg)
                if uid is not None:
                    data = json.loads(msg["data"])
                    await self._deliver_local(
                        uid, data
                    )

                for _ in range(64):
                    try:
                        extra = (
                            await pubsub.get_message(
                                ignore_subscribe_messages=True,
                                timeout=0.0,
                            )
                        )
                    except RuntimeError:
                        break
                    if not extra:
                        break
                    if extra["type"] != "message":
                        continue
                    uid = self._parse_and_deliver(
                        extra
                    )
                    if uid is not None:
                        data = json.loads(
                            extra["data"]
                        )
                        await self._deliver_local(
                            uid, data
                        )
        except asyncio.CancelledError:
            raise


ws_manager = ConnectionManager()
