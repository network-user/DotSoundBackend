from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.ws_manager import (
    _SEND_QUEUE_MAXSIZE,
    _SLOW_CONSUMER_CLOSE_CODE,
    ConnectionManager,
)

pytestmark = pytest.mark.anyio


def _make_ws() -> AsyncMock:
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


def _make_manager() -> ConnectionManager:
    mgr = ConnectionManager()
    mgr._redis = None
    mgr._pubsub = None
    return mgr


async def _wait_for(
    predicate: Callable[[], bool], *, tries: int = 500
) -> None:
    """Yield to the loop until ``predicate`` holds.

    Delivery now happens in a background writer task, so tests must
    let the loop run before asserting on the socket.
    """
    for _ in range(tries):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition not met in time")


class TestConnect:
    async def test_accept_and_register(self) -> None:
        mgr = _make_manager()
        ws = _make_ws()

        await mgr.connect(1, ws)

        ws.accept.assert_awaited_once()
        assert 1 in mgr._connections
        assert ws in mgr._connections[1]

    async def test_multiple_connections_same_user(
        self,
    ) -> None:
        mgr = _make_manager()
        ws1 = _make_ws()
        ws2 = _make_ws()

        await mgr.connect(1, ws1)
        await mgr.connect(1, ws2)

        assert len(mgr._connections[1]) == 2


class TestDisconnect:
    async def test_removes_connection(self) -> None:
        mgr = _make_manager()
        ws = _make_ws()
        await mgr.connect(1, ws)

        await mgr.disconnect(1, ws)

        assert 1 not in mgr._connections

    async def test_partial_disconnect(self) -> None:
        mgr = _make_manager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect(1, ws1)
        await mgr.connect(1, ws2)

        await mgr.disconnect(1, ws1)

        assert mgr._connections[1] == [ws2]

    async def test_disconnect_nonexistent_noop(
        self,
    ) -> None:
        mgr = _make_manager()
        ws = _make_ws()

        await mgr.disconnect(999, ws)

        assert 999 not in mgr._connections


class TestGetOnlineUserIds:
    async def test_returns_connected_ids(
        self,
    ) -> None:
        mgr = _make_manager()
        await mgr.connect(1, _make_ws())
        await mgr.connect(2, _make_ws())

        assert mgr.get_online_user_ids() == {1, 2}

    async def test_empty_when_none_connected(
        self,
    ) -> None:
        mgr = _make_manager()

        assert mgr.get_online_user_ids() == set()


class TestDeliverLocal:
    async def test_enqueues_and_writer_sends_all(
        self,
    ) -> None:
        mgr = _make_manager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect(5, ws1)
        await mgr.connect(5, ws2)
        data = {"event": "test"}

        await mgr._deliver_local(5, data)

        payload = json.dumps(data)
        await _wait_for(
            lambda: ws1.send_text.await_count == 1
            and ws2.send_text.await_count == 1
        )
        ws1.send_text.assert_awaited_once_with(payload)
        ws2.send_text.assert_awaited_once_with(payload)
        await mgr._cancel_all_writers()

    async def test_deliver_does_not_block_on_slow(
        self,
    ) -> None:
        # A stuck send on one socket must not stop the enqueue for
        # the others: _deliver_local only does put_nowait.
        mgr = _make_manager()
        block = asyncio.Event()

        async def _hang(_payload: str) -> None:
            await block.wait()

        ws_slow = _make_ws()
        ws_slow.send_text = AsyncMock(side_effect=_hang)
        ws_fast = _make_ws()
        await mgr.connect(5, ws_slow)
        await mgr.connect(5, ws_fast)

        await mgr._deliver_local(5, {"event": "x"})

        await _wait_for(lambda: ws_fast.send_text.await_count == 1)
        assert ws_slow.send_text.await_count == 1
        block.set()
        await mgr._cancel_all_writers()

    async def test_dead_socket_removed(self) -> None:
        mgr = _make_manager()
        ws_good = _make_ws()
        ws_dead = _make_ws()
        ws_dead.send_text = AsyncMock(side_effect=RuntimeError("closed"))
        await mgr.connect(5, ws_good)
        await mgr.connect(5, ws_dead)

        await mgr._deliver_local(5, {"event": "ping"})

        await _wait_for(lambda: ws_dead not in mgr._connections.get(5, []))
        assert ws_good in mgr._connections[5]
        assert ws_dead not in mgr._ws_state
        await mgr._cancel_all_writers()


class TestSendToUser:
    async def test_publishes_to_redis(self) -> None:
        mgr = _make_manager()
        mgr._redis = AsyncMock()
        mgr._redis.publish = AsyncMock()
        data = {"event": "new_message"}

        await mgr.send_to_user(42, data)

        mgr._redis.publish.assert_awaited_once_with(
            "user:42", json.dumps(data)
        )

    async def test_no_redis_noop(self) -> None:
        mgr = _make_manager()
        mgr._redis = None

        await mgr.send_to_user(42, {"event": "test"})


class TestBroadcastToOnline:
    async def test_sends_to_all_online(self) -> None:
        mgr = _make_manager()
        mgr._redis = AsyncMock()
        mgr._redis.publish = AsyncMock()
        await mgr.connect(1, _make_ws())
        await mgr.connect(2, _make_ws())
        data = {"event": "broadcast"}

        await mgr.broadcast_to_online(data)

        assert mgr._redis.publish.await_count == 2


class TestParseAndDeliver:
    def test_valid_channel(self) -> None:
        mgr = _make_manager()
        msg = {
            "channel": "user:42",
            "data": "{}",
        }

        assert mgr._parse_and_deliver(msg) == 42

    def test_invalid_channel_prefix(self) -> None:
        mgr = _make_manager()
        msg = {
            "channel": "other:42",
            "data": "{}",
        }

        assert mgr._parse_and_deliver(msg) is None

    def test_bytes_channel(self) -> None:
        mgr = _make_manager()
        msg = {
            "channel": b"user:7",
            "data": "{}",
        }

        assert mgr._parse_and_deliver(msg) == 7

    def test_non_numeric_uid(self) -> None:
        mgr = _make_manager()
        msg = {
            "channel": "user:abc",
            "data": "{}",
        }

        assert mgr._parse_and_deliver(msg) is None


class TestSendToConversation:
    async def test_sends_to_all_members(
        self,
    ) -> None:
        mgr = _make_manager()
        mgr._redis = AsyncMock()
        mgr._redis.publish = AsyncMock()
        data = {"event": "new_msg"}

        await mgr.send_to_conversation([1, 2, 3], data)

        assert mgr._redis.publish.await_count == 3


class TestBroadcastActivity:
    async def test_skips_sender(self) -> None:
        mgr = _make_manager()
        mgr._redis = AsyncMock()
        mgr._redis.publish = AsyncMock()

        await mgr.broadcast_activity(
            user_id=1,
            conversation_id=10,
            member_ids=[1, 2, 3],
            activity="typing",
        )

        assert mgr._redis.publish.await_count == 2

    async def test_no_other_members(
        self,
    ) -> None:
        mgr = _make_manager()
        mgr._redis = AsyncMock()
        mgr._redis.publish = AsyncMock()

        await mgr.broadcast_activity(
            user_id=1,
            conversation_id=10,
            member_ids=[1],
            activity="typing",
        )

        mgr._redis.publish.assert_not_awaited()


class TestPresence:
    async def test_get_presence_no_redis(
        self,
    ) -> None:
        mgr = _make_manager()
        mgr._redis = None

        p = await mgr.get_presence(1)

        assert p["status"] == "offline"

    async def test_get_presence_not_found(
        self,
    ) -> None:
        mgr = _make_manager()
        mgr._redis = AsyncMock()
        mgr._redis.get = AsyncMock(return_value=None)

        p = await mgr.get_presence(99)

        assert p["status"] == "offline"

    async def test_get_presence_found(
        self,
    ) -> None:
        mgr = _make_manager()
        mgr._redis = AsyncMock()
        mgr._redis.get = AsyncMock(
            return_value=json.dumps({"status": "online", "ts": 123.0})
        )

        p = await mgr.get_presence(1)

        assert p["status"] == "online"
        assert p["ts"] == 123.0

    async def test_get_presence_bulk(
        self,
    ) -> None:
        mgr = _make_manager()
        mgr._redis = AsyncMock()
        mgr._redis.mget = AsyncMock(
            return_value=[
                json.dumps({"status": "online", "ts": 1.0}),
                None,
            ]
        )

        result = await mgr.get_presence_bulk([1, 2])

        assert len(result) == 2
        assert result[1]["status"] == "online"
        assert result[2]["status"] == "offline"

    async def test_set_presence_online(
        self,
    ) -> None:
        mgr = _make_manager()
        mgr._redis = AsyncMock()
        mgr._redis.set = AsyncMock()

        await mgr._set_presence(1, "online")

        mgr._redis.set.assert_awaited_once()

    async def test_set_presence_offline(
        self,
    ) -> None:
        mgr = _make_manager()
        mgr._redis = AsyncMock()
        mgr._redis.set = AsyncMock()

        await mgr._set_presence(1, "offline")

        mgr._redis.set.assert_awaited_once()

    async def test_set_presence_no_redis(
        self,
    ) -> None:
        mgr = _make_manager()
        mgr._redis = None

        await mgr._set_presence(1, "online")


class TestShutdown:
    async def test_shutdown_cleans_up(
        self,
    ) -> None:
        mgr = _make_manager()
        mgr._redis = AsyncMock()
        mgr._redis.delete = AsyncMock()
        mgr._redis.aclose = AsyncMock()
        ws = _make_ws()
        await mgr.connect(1, ws)

        await mgr.shutdown()

        mgr._redis.aclose.assert_awaited_once()


class TestSlowConsumerEviction:
    async def test_queue_overflow_evicts_and_closes(
        self,
    ) -> None:
        mgr = _make_manager()
        block = asyncio.Event()

        async def _hang(_payload: str) -> None:
            await block.wait()

        ws = _make_ws()
        ws.send_text = AsyncMock(side_effect=_hang)
        await mgr.connect(9, ws)

        # The writer is stuck, so the bounded queue fills and the
        # next put_nowait overflows -> the slow client is evicted.
        for i in range(_SEND_QUEUE_MAXSIZE + 5):
            await mgr._deliver_local(9, {"event": "e", "i": i})

        # Teardown+close now runs as a detached task off the hot path,
        # so let the loop run it before asserting. Repeated overflows
        # schedule several teardowns for the same socket; the idempotent
        # guard means only the first does the work and close() fires once.
        await _wait_for(lambda: 9 not in mgr._connections)
        assert ws not in mgr._ws_state
        ws.close.assert_awaited_once_with(code=_SLOW_CONSUMER_CLOSE_CODE)
        block.set()

    async def test_survivors_keep_receiving(
        self,
    ) -> None:
        mgr = _make_manager()
        block = asyncio.Event()

        async def _hang(_payload: str) -> None:
            await block.wait()

        ws_slow = _make_ws()
        ws_slow.send_text = AsyncMock(side_effect=_hang)
        ws_ok = _make_ws()
        await mgr.connect(9, ws_slow)
        await mgr.connect(9, ws_ok)

        for i in range(_SEND_QUEUE_MAXSIZE + 5):
            await mgr._deliver_local(9, {"event": "e", "i": i})
            # Mirror the real burst loop in _listen_redis, which now
            # yields (await asyncio.sleep(0)) after each message so the
            # per-connection writers drain between enqueues. The healthy
            # writer keeps up and only the stuck socket's queue fills.
            await asyncio.sleep(0)

        # slow one gone, healthy one still registered + draining.
        assert ws_slow not in mgr._connections.get(9, [])
        assert ws_ok in mgr._connections.get(9, [])
        await _wait_for(lambda: ws_ok.send_text.await_count >= 1)
        block.set()
        await mgr._cancel_all_writers()


class TestSafeProcess:
    async def test_bad_payload_is_swallowed(
        self,
    ) -> None:
        mgr = _make_manager()
        ws = _make_ws()
        await mgr.connect(1, ws)
        msg = {
            "type": "message",
            "channel": "user:1",
            "data": "{not-json",
        }

        # Must not raise: a broken payload cannot kill the listener.
        await mgr._safe_process(msg)

        ws.send_text.assert_not_awaited()
        await mgr._cancel_all_writers()

    async def test_bad_then_good_still_delivers(
        self,
    ) -> None:
        mgr = _make_manager()
        ws = _make_ws()
        await mgr.connect(1, ws)

        await mgr._safe_process(
            {
                "type": "message",
                "channel": "user:1",
                "data": "{broken",
            }
        )
        await mgr._safe_process(
            {
                "type": "message",
                "channel": "user:1",
                "data": json.dumps({"event": "ok"}),
            }
        )

        await _wait_for(lambda: ws.send_text.await_count == 1)
        ws.send_text.assert_awaited_once_with(json.dumps({"event": "ok"}))
        await mgr._cancel_all_writers()

    async def test_cancelled_error_propagates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mgr = _make_manager()

        async def _boom(_msg: dict[str, Any]) -> None:
            raise asyncio.CancelledError

        monkeypatch.setattr(mgr, "_process_message", _boom)

        with pytest.raises(asyncio.CancelledError):
            await mgr._safe_process(
                {
                    "type": "message",
                    "channel": "user:1",
                    "data": "{}",
                }
            )


class TestConnectionCleanup:
    async def test_disconnect_cancels_writer(
        self,
    ) -> None:
        mgr = _make_manager()
        ws = _make_ws()
        await mgr.connect(1, ws)
        await mgr._deliver_local(1, {"event": "x"})
        state = mgr._ws_state[ws]
        assert state.writer is not None
        writer = state.writer

        await mgr.disconnect(1, ws)

        assert ws not in mgr._ws_state
        assert 1 not in mgr._connections
        assert writer.done()

    async def test_connect_registers_queue(
        self,
    ) -> None:
        mgr = _make_manager()
        ws = _make_ws()

        await mgr.connect(1, ws)

        assert ws in mgr._ws_state
        assert mgr._ws_state[ws].writer is None
        await mgr.disconnect(1, ws)


class TestUnsubscribeSerialization:
    async def test_concurrent_unsubscribe_serialized(
        self,
    ) -> None:
        mgr = _make_manager()
        mgr._pubsub = AsyncMock()
        mgr._pubsub.subscribe = AsyncMock()
        counters = {"cur": 0, "max": 0}

        async def _unsub(_channel: str) -> None:
            counters["cur"] += 1
            counters["max"] = max(counters["max"], counters["cur"])
            await asyncio.sleep(0.01)
            counters["cur"] -= 1

        mgr._pubsub.unsubscribe = AsyncMock(side_effect=_unsub)
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect(1, ws1)
        await mgr.connect(2, ws2)

        await asyncio.gather(
            mgr.disconnect(1, ws1),
            mgr.disconnect(2, ws2),
        )

        assert counters["max"] == 1
        assert mgr._pubsub.unsubscribe.await_count == 2
