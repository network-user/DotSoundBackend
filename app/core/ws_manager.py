from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass
from typing import Any

import structlog
from fastapi import WebSocket
from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


_PRESENCE_TTL = 120
_PRESENCE_PREFIX = "presence:"
_MAX_WS_PER_USER = 6

# Per-connection outbound queue. A dedicated writer task drains it
# into the socket, so a single slow client (full TCP send buffer)
# can no longer stall fan-out delivery to every other connection.
_SEND_QUEUE_MAXSIZE = 100
# Close code for a client whose outbound queue overflowed because it
# could not keep up. Mirrors the module's custom 4xxx convention
# (cf. 4429 for the per-user cap); 4408 ~ HTTP 408 "peer too slow".
_SLOW_CONSUMER_CLOSE_CODE = 4408

ACTIVITY_TYPES = frozenset(
    {
        "typing",
        "recording_audio",
        "sending_photo",
        "idle",
    }
)


@dataclass
class _WsState:
    """Per-socket delivery state: a bounded queue and its writer."""

    queue: asyncio.Queue[str]
    writer: asyncio.Task[None] | None = None


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, list[WebSocket]] = {}
        self._ws_state: dict[WebSocket, _WsState] = {}
        self._redis: Redis | None = None  # type: ignore[type-arg]
        self._pubsub: PubSub | None = None
        self._pubsub_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        # Slow-consumer evictions run as detached tasks so a hung
        # ``ws.close()`` never blocks the redis listener. Keep strong
        # refs (asyncio only holds weak ones) until each task finishes.
        self._eviction_tasks: set[asyncio.Task[None]] = set()
        # Serializes pubsub subscribe/unsubscribe so parallel
        # (dis)connects cannot corrupt the shared pubsub command
        # stream with interleaved writes.
        self._pubsub_lock: asyncio.Lock = asyncio.Lock()

    async def startup(self) -> None:
        self._redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._pubsub = self._redis.pubsub()
        self._pubsub_task = asyncio.create_task(self._listen_redis())
        self._heartbeat_task = asyncio.create_task(self._presence_heartbeat())
        logger.info("ws_manager_started")

    async def shutdown(self) -> None:
        for task in (
            self._pubsub_task,
            self._heartbeat_task,
        ):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        for evict_task in list(self._eviction_tasks):
            evict_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await evict_task
        self._eviction_tasks.clear()
        await self._cancel_all_writers()
        if self._pubsub:
            await self._pubsub.aclose()
        if self._redis:
            for uid in list(self._connections):
                await self._redis.delete(f"{_PRESENCE_PREFIX}{uid}")
            await self._redis.aclose()
        logger.info("ws_manager_stopped")

    async def _cancel_all_writers(self) -> None:
        for state in list(self._ws_state.values()):
            writer = state.writer
            if (
                writer is not None
                and not writer.done()
                and writer is not asyncio.current_task()
            ):
                writer.cancel()
                try:
                    await writer
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.debug("ws_writer_shutdown_error")
        self._ws_state.clear()

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
        self._connections.setdefault(user_id, []).append(ws)
        self._ws_state[ws] = _WsState(
            queue=asyncio.Queue(maxsize=_SEND_QUEUE_MAXSIZE)
        )
        if is_first and self._pubsub:
            async with self._pubsub_lock:
                await self._pubsub.subscribe(f"user:{user_id}")
        if self._redis:
            await self._set_presence(user_id, "online")
        logger.debug("ws_connected", user_id=user_id)
        return True

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        await self._teardown_connection(user_id, ws)

    async def _teardown_connection(
        self,
        user_id: int,
        ws: WebSocket,
        *,
        close_code: int | None = None,
    ) -> None:
        """Full, idempotent cleanup for a single socket.

        Cancels the writer task, drops its queue, removes the socket
        from the user's connection list and, when it was the last one
        for that user, unsubscribes (serialized) and marks the user
        offline. Optionally closes the socket with ``close_code``
        (used to actively evict a slow consumer).
        """
        state = self._ws_state.pop(ws, None)
        if state is None:
            # Already torn down. Happens when a slow-consumer eviction
            # is scheduled more than once (the bounded queue keeps
            # overflowing before the detached teardown runs) or when an
            # explicit disconnect races the writer's own failure
            # teardown. The call that popped the state owns the full
            # cleanup and completes it, so every later call is a no-op;
            # this is what keeps ``ws.close()`` from firing twice.
            return
        await self._stop_writer(state, user_id)
        conns = self._connections.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(user_id, None)
            if self._pubsub:
                async with self._pubsub_lock:
                    try:
                        await self._pubsub.unsubscribe(f"user:{user_id}")
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.debug(
                            "ws_unsubscribe_error",
                            user_id=user_id,
                        )
            if self._redis:
                await self._set_presence(user_id, "offline")
        if close_code is not None:
            with contextlib.suppress(Exception):
                await ws.close(code=close_code)
        logger.debug("ws_disconnected", user_id=user_id)

    async def _stop_writer(self, state: _WsState, user_id: int) -> None:
        writer = state.writer
        if writer is None or writer.done():
            return
        if writer is asyncio.current_task():
            # Called from inside the writer itself (its send
            # failed): don't cancel/await self, just let it unwind.
            return
        writer.cancel()
        try:
            await writer
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.debug(
                "ws_writer_teardown_error",
                user_id=user_id,
            )

    def _on_eviction_done(self, task: asyncio.Task[None]) -> None:
        """Drop the finished eviction task and log any real failure."""
        self._eviction_tasks.discard(task)
        if task.cancelled():
            return
        if task.exception() is not None:
            logger.debug("ws_slow_consumer_teardown_error")

    def get_online_user_ids(self) -> set[int]:
        return set(self._connections.keys())

    async def send_to_user(self, user_id: int, data: dict[str, Any]) -> None:
        if self._redis:
            await self._redis.publish(f"user:{user_id}", json.dumps(data))

    async def send_to_conversation(
        self,
        member_ids: list[int],
        data: dict[str, Any],
    ) -> None:
        for uid in member_ids:
            await self.send_to_user(uid, data)

    async def broadcast_to_online(self, data: dict[str, Any]) -> None:
        for uid in list(self._connections.keys()):
            await self.send_to_user(uid, data)

    async def _set_presence(self, user_id: int, status: str) -> None:
        if not self._redis:
            return
        import time

        key = f"{_PRESENCE_PREFIX}{user_id}"
        value = json.dumps({"status": status, "ts": time.time()})
        if status == "offline":
            await self._redis.set(key, value, ex=86400 * 7)
        else:
            await self._redis.set(key, value, ex=_PRESENCE_TTL)

    async def get_presence(self, user_id: int) -> dict[str, Any]:
        if not self._redis:
            return {"status": "offline", "ts": 0}
        raw = await self._redis.get(f"{_PRESENCE_PREFIX}{user_id}")
        if not raw:
            return {"status": "offline", "ts": 0}
        return json.loads(raw)  # type: ignore[no-any-return]

    async def get_presence_bulk(
        self, user_ids: list[int]
    ) -> dict[int, dict[str, Any]]:
        if not user_ids:
            return {}
        if not self._redis:
            return {uid: {"status": "offline", "ts": 0} for uid in user_ids}
        keys = [f"{_PRESENCE_PREFIX}{uid}" for uid in user_ids]
        raws = await self._redis.mget(keys)
        result: dict[int, dict[str, Any]] = {}
        for uid, raw in zip(user_ids, raws, strict=False):
            if not raw:
                result[uid] = {"status": "offline", "ts": 0}
                continue
            try:
                result[uid] = json.loads(raw)
            except (TypeError, ValueError):
                result[uid] = {"status": "offline", "ts": 0}
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
        async for key in self._redis.scan_iter(match=pattern):
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
                for uid in list(self._connections.keys()):
                    await self._set_presence(uid, "online")
                await asyncio.sleep(_PRESENCE_TTL // 2)
        except asyncio.CancelledError:
            raise

    async def _deliver_local(self, user_id: int, data: dict[str, Any]) -> None:
        conns = self._connections.get(user_id, []).copy()
        if not conns:
            logger.debug(
                "ws_no_local_conns",
                user_id=user_id,
                ws_event=data.get("event"),
            )
            return
        payload = json.dumps(data)
        evicted: list[WebSocket] = []
        for ws in conns:
            state = self._ws_state.get(ws)
            if state is None:
                continue
            if state.writer is None or state.writer.done():
                state.writer = asyncio.create_task(
                    self._writer_loop(user_id, ws, state.queue)
                )
            try:
                state.queue.put_nowait(payload)
            except asyncio.QueueFull:
                evicted.append(ws)
        for ws in evicted:
            logger.warning(
                "ws_slow_consumer_evicted",
                user_id=user_id,
                ws_event=data.get("event"),
                maxsize=_SEND_QUEUE_MAXSIZE,
            )
            # Detach teardown+close from the hot path: a hung
            # ``ws.close()`` on the evicted socket must never block
            # fan-out delivery to every other connection. The teardown
            # is idempotent, so a repeat eviction before it runs is a
            # no-op.
            task = asyncio.create_task(
                self._teardown_connection(
                    user_id,
                    ws,
                    close_code=_SLOW_CONSUMER_CLOSE_CODE,
                )
            )
            self._eviction_tasks.add(task)
            task.add_done_callback(self._on_eviction_done)
        logger.debug(
            "ws_enqueued",
            user_id=user_id,
            ws_event=data.get("event"),
            count=len(conns) - len(evicted),
        )

    async def _writer_loop(
        self,
        user_id: int,
        ws: WebSocket,
        queue: asyncio.Queue[str],
    ) -> None:
        """Drain one socket's queue; on send failure, tear it down.

        Runs one per connection so a blocked ``send_text`` only backs
        up that client's own bounded queue, never the shared listener.
        """
        try:
            while True:
                payload = await queue.get()
                try:
                    await ws.send_text(payload)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.debug(
                        "ws_send_failed",
                        user_id=user_id,
                    )
                    await self._teardown_connection(user_id, ws)
                    return
        except asyncio.CancelledError:
            raise

    def _parse_and_deliver(self, msg: dict[str, Any]) -> int | None:
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

    async def _process_message(self, msg: dict[str, Any]) -> None:
        uid = self._parse_and_deliver(msg)
        if uid is None:
            return
        data = json.loads(msg["data"])
        await self._deliver_local(uid, data)

    async def _safe_process(self, msg: dict[str, Any]) -> None:
        """Process one pubsub message, isolating its failures.

        A single malformed payload (bad JSON, unexpected shape) must
        not kill the listener and freeze delivery for everyone until
        a restart, so anything other than cancellation is logged and
        swallowed.
        """
        try:
            await self._process_message(msg)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "ws_message_process_failed",
                channel=msg.get("channel"),
                exc_info=True,
            )

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

                await self._safe_process(msg)

                for _ in range(64):
                    try:
                        extra = await pubsub.get_message(
                            ignore_subscribe_messages=True,
                            timeout=0.0,
                        )
                    except RuntimeError:
                        break
                    if not extra:
                        break
                    if extra["type"] != "message":
                        continue
                    await self._safe_process(extra)
                    # Yield so the per-connection writer tasks get a
                    # turn to drain their queues between enqueues. Without
                    # this, a burst enqueues faster than any writer can
                    # run and a live, healthy client hits QueueFull and
                    # is wrongly evicted as "slow".
                    await asyncio.sleep(0)
        except asyncio.CancelledError:
            raise


ws_manager = ConnectionManager()
