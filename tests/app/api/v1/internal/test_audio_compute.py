"""Unit tests for the SoundCloud proxy stream watchdog.

The full ``download_audio`` endpoint is exercised via integration
tests with workers; here we just pin the chunk-idle behaviour of
``_stream_sc_cdn_to_worker`` so a stalled CDN never holds the
worker for the full httpx ``read=`` budget.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import pytest

from app.api.v1.internal import audio_compute as ac

pytestmark = pytest.mark.anyio


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
    def __init__(self, *_a: Any, **_kw: Any) -> None:
        return

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *_a: object) -> None:
        return

    def stream(self, _method: str, _url: str) -> _StreamCM:
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
