"""Unit tests for the SoundCloud proxy stream watchdog.

The full ``download_audio`` endpoint is exercised via integration
tests with workers; here we just pin the chunk-idle behaviour of
``_stream_sc_cdn_to_worker`` so a stalled CDN never holds the
worker for the full httpx ``read=`` budget.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import time
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.internal import audio_compute as ac
from app.models.lyrics_job import LyricsJob
from app.models.track import Track
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


async def test_sc_proxy_materializes_temp_file_and_deletes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    temp_path = tmp_path / "audio.audio"

    def _mkstemp(**_kwargs: object) -> tuple[int, str]:
        fd = os.open(
            temp_path,
            os.O_CREAT | os.O_RDWR | os.O_TRUNC,
            0o600,
        )
        return fd, str(temp_path)

    class _ChunkResp:
        def raise_for_status(self) -> None:
            return

        def aiter_bytes(self, _chunk_size: int) -> AsyncIterator[bytes]:
            async def _gen() -> AsyncIterator[bytes]:
                yield b"abc"
                yield b"def"

            return _gen()

    class _ChunkStreamCM:
        async def __aenter__(self) -> _ChunkResp:
            return _ChunkResp()

        async def __aexit__(self, *_a: object) -> None:
            return

    class _ChunkClient:
        def __init__(self, *_a: object, **_kw: object) -> None:
            return

        async def __aenter__(self) -> _ChunkClient:
            return self

        async def __aexit__(self, *_a: object) -> None:
            return

        def stream(
            self,
            _method: str,
            _url: str,
            **_kwargs: object,
        ) -> _ChunkStreamCM:
            return _ChunkStreamCM()

    monkeypatch.setattr(ac.tempfile, "mkstemp", _mkstemp)
    monkeypatch.setattr(ac.httpx, "AsyncClient", _ChunkClient)

    chunks = [
        chunk
        async for chunk in ac._stream_sc_cdn_to_worker(
            "https://cf-media.sndcdn.com/media/abc.mp3",
            job_id="lj_materialize",
            chunk_idle_timeout=0.05,
        )
    ]

    assert b"".join(chunks) == b"abcdef"
    assert not temp_path.exists()


@patch(
    f"{_APIM}.rl.check_and_consume",
    new_callable=AsyncMock,
)
@patch(
    f"{_ALL}.is_ip_in_cidrs",
    return_value=True,
)
async def test_audio_download_proxy_bypasses_disabled_direct_external_gate(
    _allowlist: object,
    _rate_limit: object,
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.services.soundcloud_service import SoundCloudService

    class _ChunkResp:
        def raise_for_status(self) -> None:
            return

        def aiter_bytes(self, _chunk_size: int) -> AsyncIterator[bytes]:
            async def _gen() -> AsyncIterator[bytes]:
                yield b"audio"

            return _gen()

    class _ChunkStreamCM:
        async def __aenter__(self) -> _ChunkResp:
            return _ChunkResp()

        async def __aexit__(self, *_a: object) -> None:
            return

    class _ChunkClient:
        def __init__(self, *_a: object, **_kw: object) -> None:
            return

        async def __aenter__(self) -> _ChunkClient:
            return self

        async def __aexit__(self, *_a: object) -> None:
            return

        def stream(
            self,
            _method: str,
            _url: str,
            **_kwargs: object,
        ) -> _ChunkStreamCM:
            return _ChunkStreamCM()

    monkeypatch.setattr(
        ac.settings,
        "worker_third_party_audio_enabled",
        False,
    )
    monkeypatch.setattr(ac.settings, "sc_client_id", "test-client")
    monkeypatch.setattr(ac.httpx, "AsyncClient", _ChunkClient)
    monkeypatch.setattr(
        SoundCloudService,
        "get_stream_info",
        AsyncMock(
            return_value=(
                "https://cf-media.sndcdn.com/media/progressive.mp3",
                "progressive",
            )
        ),
    )

    worker, _secret = await cws.register_worker(
        db_session,
        name="asr-proxy",
        profile="gpu_full",
    )
    track = Track(
        title="External",
        artist="Artist",
        sc_url="https://soundcloud.com/a/t",
        is_active=True,
        is_public=True,
        source="soundcloud",
    )
    db_session.add(track)
    await db_session.flush()
    job = LyricsJob(
        id="lj_proxy_disabled",
        track_id=track.id,
        progress_id="progress_proxy_disabled",
        profile="gpu_full",
        status="running",
        routed_to_worker=worker.id,
    )
    db_session.add(job)
    job_id = job.id
    worker_id = worker.id
    await db_session.commit()

    token = cws.generate_single_use_token(job_id, worker_id)
    path = (
        f"/api/v1/internal/audio-compute/audio/{job_id}"
        f"?ott={token}&proxy=1"
    )
    response = await client.get(path, headers={"X-Worker-Id": worker_id})

    assert response.status_code == 200
    assert response.content == b"audio"


@patch(
    f"{_ALL}.is_ip_in_cidrs",
    return_value=True,
)
@patch(
    f"{_WCS}.get_redis_client",
    new_callable=_mock_redis,
)
async def test_unknown_worker_404_is_audited_with_reason(
    _redis: object,
    _allowlist: object,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    path = "/api/v1/internal/audio-compute/jobs/claim"
    headers = {
        "X-Worker-Id": "w_missing",
        "X-Timestamp": str(int(time.time())),
        "X-Nonce": secrets.token_hex(8),
        "X-Worker-Signature": "0" * 64,
    }

    response = await client.post(path, headers=headers, content=b"")

    assert response.status_code == 404
    audit = (
        await db_session.execute(
            select(WorkerAuditLog).where(
                WorkerAuditLog.worker_id == "w_missing",
                WorkerAuditLog.action == "auth_fail",
            )
        )
    ).scalar_one()
    assert audit.status_code == 404
    assert audit.meta is not None
    assert audit.meta["reason"] == "unknown_or_inactive"
    assert audit.meta["path"] == path


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
