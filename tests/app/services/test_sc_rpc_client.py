from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

import pytest
from dotsound_private_core.contracts.sc_rpc_protocol import (
    SoundCloudRpcMethod,
)

from app.services import sc_rpc_client

pytestmark = pytest.mark.anyio


class _FakeRedisGet:
    def __init__(self, payload: bytes | None) -> None:
        self.payload = payload

    async def get(self, _key: str) -> bytes | None:
        return self.payload


class _AlwaysEmptyRedis:
    async def get(self, _key: str) -> bytes | None:
        return None


class _StubJob:
    def __init__(self, request_id: str) -> None:
        self.id = 1
        self.target_id = request_id


@asynccontextmanager
async def _dummy_session_ctx() -> Any:
    class _S:
        async def commit(self) -> None:
            return None

    yield _S()


async def _enqueue_stub(
    _session: Any,
    *,
    method: str,
    args: dict[str, Any],
    sticky_key: str = "",
    request_id: str | None = None,
    timeout_seconds: float = 0.0,
) -> _StubJob:
    return _StubJob(request_id or f"req-{method}")


def _wire_offload_path(
    monkeypatch: pytest.MonkeyPatch,
    *,
    redis: object,
    enabled: bool = True,
) -> None:
    monkeypatch.setattr(
        sc_rpc_client, "offload_enabled", lambda: enabled
    )
    monkeypatch.setattr(
        sc_rpc_client, "_wait_timeout", lambda: 1.0
    )
    monkeypatch.setattr(
        sc_rpc_client, "get_redis_client", lambda: redis
    )
    monkeypatch.setattr(
        sc_rpc_client,
        "AsyncSessionLocal",
        lambda: _dummy_session_ctx(),
    )
    monkeypatch.setattr(
        sc_rpc_client.q, "enqueue_soundcloud_rpc", _enqueue_stub
    )


async def test_call_offload_disabled_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sc_rpc_client, "offload_enabled", lambda: False
    )
    with pytest.raises(sc_rpc_client.ScRpcOffloadDisabled):
        await sc_rpc_client.call_soundcloud_rpc(
            SoundCloudRpcMethod.RESOLVE,
            args={"url": "https://soundcloud.com/x"},
        )


async def test_call_success_returns_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = {
        "request_id": "req-resolve",
        "success": True,
        "data": {"id": 42, "title": "t"},
    }
    payload = json.dumps({"envelope": envelope}).encode()
    _wire_offload_path(
        monkeypatch, redis=_FakeRedisGet(payload)
    )

    data = await sc_rpc_client.call_soundcloud_rpc(
        SoundCloudRpcMethod.RESOLVE,
        args={"url": "https://soundcloud.com/x"},
        request_id="req-resolve",
    )
    assert data == {"id": 42, "title": "t"}


async def test_call_unreachable_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_offload_path(
        monkeypatch, redis=_AlwaysEmptyRedis()
    )
    monkeypatch.setattr(
        sc_rpc_client, "_wait_timeout", lambda: 0.05
    )

    with pytest.raises(sc_rpc_client.ScRpcUnreachable):
        await sc_rpc_client.call_soundcloud_rpc(
            SoundCloudRpcMethod.FETCH_TRACK,
            args={"track_id": 1},
            request_id="req-miss",
        )


async def test_call_upstream_error_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = {
        "request_id": "req-dead",
        "success": False,
        "error_kind": "dead_track",
        "error_message": "track 404",
        "upstream_status": 404,
    }
    payload = json.dumps({"envelope": envelope}).encode()
    _wire_offload_path(
        monkeypatch, redis=_FakeRedisGet(payload)
    )

    with pytest.raises(
        sc_rpc_client.ScRpcUpstreamError
    ) as excinfo:
        await sc_rpc_client.call_soundcloud_rpc(
            SoundCloudRpcMethod.FETCH_TRACK,
            args={"track_id": 1},
            request_id="req-dead",
        )
    assert excinfo.value.error_kind == "dead_track"
    assert excinfo.value.upstream_status == 404


async def test_wait_for_envelope_handles_bad_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_offload_path(
        monkeypatch, redis=_FakeRedisGet(b"not-json")
    )

    with pytest.raises(sc_rpc_client.ScRpcUnreachable):
        await sc_rpc_client.call_soundcloud_rpc(
            SoundCloudRpcMethod.FETCH_TRACK,
            args={"track_id": 1},
            request_id="req-broken",
        )


async def test_wait_for_envelope_swallows_redis_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Boom:
        async def get(self, _key: str) -> None:
            raise RuntimeError("redis down")

    _wire_offload_path(monkeypatch, redis=_Boom())
    with pytest.raises(sc_rpc_client.ScRpcUnreachable):
        await sc_rpc_client.call_soundcloud_rpc(
            SoundCloudRpcMethod.FETCH_TRACK,
            args={"track_id": 1},
            request_id="req-redis-down",
        )
