from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.ws_manager import ConnectionManager

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
    async def test_sends_to_all_sockets(
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
        ws1.send_text.assert_awaited_once_with(payload)
        ws2.send_text.assert_awaited_once_with(payload)

    async def test_dead_socket_removed(self) -> None:
        mgr = _make_manager()
        ws_good = _make_ws()
        ws_dead = _make_ws()
        ws_dead.send_text = AsyncMock(
            side_effect=RuntimeError("closed")
        )
        await mgr.connect(5, ws_good)
        await mgr.connect(5, ws_dead)

        await mgr._deliver_local(
            5, {"event": "ping"}
        )

        assert ws_dead not in mgr._connections.get(
            5, []
        )
        assert ws_good in mgr._connections[5]


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

        await mgr.send_to_user(
            42, {"event": "test"}
        )


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

        await mgr.send_to_conversation(
            [1, 2, 3], data
        )

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
        mgr._redis.get = AsyncMock(
            return_value=None
        )

        p = await mgr.get_presence(99)

        assert p["status"] == "offline"

    async def test_get_presence_found(
        self,
    ) -> None:
        mgr = _make_manager()
        mgr._redis = AsyncMock()
        mgr._redis.get = AsyncMock(
            return_value=json.dumps(
                {"status": "online", "ts": 123.0}
            )
        )

        p = await mgr.get_presence(1)

        assert p["status"] == "online"
        assert p["ts"] == 123.0

    async def test_get_presence_bulk(
        self,
    ) -> None:
        mgr = _make_manager()
        mgr._redis = AsyncMock()
        mgr._redis.get = AsyncMock(
            return_value=json.dumps(
                {"status": "online", "ts": 1.0}
            )
        )

        result = await mgr.get_presence_bulk(
            [1, 2]
        )

        assert len(result) == 2
        assert result[1]["status"] == "online"

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
