"""Unit tests for the SoundCloud proxy stream watchdog.

The full ``download_audio`` endpoint is exercised via integration
tests with workers; here we just pin the chunk-idle behaviour of
``_stream_sc_cdn_to_worker`` so a stalled CDN never holds the
worker for the full httpx ``read=`` budget.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.internal import audio_compute as ac
from app.models.worker_audit import WorkerAuditLog
from app.services import compute_worker_service as cws

pytestmark = pytest.mark.anyio

_APIM = "app.api.v1.internal.audio_compute"
_WCS = "app.services.compute_worker_service"
_ALL = "app.middlewares.internal_api_allowlist"


def _w_headers(
    worker: object,
    method: str,
    path: str,
    body: bytes,
) -> dict[str, str]:
    ts = str(int(time.time()))
    nonce = secrets.token_hex(8)
    sig = cws._compute_signature(
        worker.token_hash,
        method,
        path,
        ts,
        nonce,
        body,
    )
    return {
        "X-Worker-Id": worker.id,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Worker-Signature": sig,
    }


def _mock_redis() -> MagicMock:
    redis = MagicMock()
    redis.set = AsyncMock(return_value=True)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    return MagicMock(return_value=redis)


class _StallingResp:
    def raise_for_status(self) -> None:
        return

    def aiter_bytes(self, _chunk_size: int) -> AsyncIterator[bytes]:
        async def _gen() -> AsyncIterator[bytes]:
            await asyncio.sleep(5.0)
            yield b"never"

        return _gen()


class _StreamCM:
    async def __aenter__(self) -> _StallingResp:
        return _StallingResp()

    async def __aexit__(self, *_a: object) -> None:
        return


class _FakeAsyncClient:
    def __init__(self, *_a: object, **_kw: object) -> None:
        return

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *_a: object) -> None:
        return

    def stream(
        self,
        _method: str,
        _url: str,
        **_kwargs: object,
    ) -> _StreamCM:
        return _StreamCM()


async def test_sc_proxy_chunk_idle_aborts_stalled_stream() -> None:
    with patch.object(ac.httpx, "AsyncClient", _FakeAsyncClient):
        gen = ac._stream_sc_cdn_to_worker(
            "https://cf-hls-media.example/track/preview.mp3",
            job_id="lj_test",
            chunk_idle_timeout=0.05,
        )
        with pytest.raises(asyncio.TimeoutError):
            async for _ in gen:
                pass


@patch(
    f"{_APIM}.rl.check_and_consume",
    new_callable=AsyncMock,
)
@patch(
    f"{_ALL}.is_ip_in_cidrs",
    return_value=True,
)
@patch(
    f"{_WCS}.get_redis_client",
    new_callable=_mock_redis,
)
async def test_audio_claim_empty_audit_includes_reason(
    _redis: object,
    _allowlist: object,
    _rate_limit: object,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    worker, _secret = await cws.register_worker(
        db_session,
        name="asr-empty",
        profile="gpu_full",
    )
    await db_session.commit()
    path = "/api/v1/internal/audio-compute/jobs/claim"
    body = b""
    response = await client.post(
        path,
        headers=_w_headers(worker, "POST", path, body),
        content=body,
    )

    assert response.status_code == 204
    audit = (
        await db_session.execute(
            select(WorkerAuditLog).where(
                WorkerAuditLog.worker_id == worker.id,
                WorkerAuditLog.action == "claim_empty",
            )
        )
    ).scalar_one()
    assert audit.meta is not None
    assert audit.meta["reason"] == "no_queued_jobs"
    assert audit.meta["claim_profiles"] == ["gpu_full"]
    assert audit.meta["queued_total"] == 0
