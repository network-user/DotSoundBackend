"""Unit tests for the audio_cache_worker download path.

Focus: byte-level downloads must go through the shared streaming
egress pool (sticky-per-track, quarantine-aware), not through bare
``httpx`` with the server's native IP. The DB / blob storage path is
covered by integration tests elsewhere; here we only exercise
``_download_bytes`` and ``_proxy_service_for_platform``.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.services import audio_cache_worker
from app.services.audio_cache_worker import (
    _download_bytes,
    _proxy_service_for_platform,
)
from app.services.streaming_egress_pool import (
    StreamingEgressDecision,
    get_streaming_egress_pool,
)


@pytest.fixture(autouse=True)
def _reset_pool() -> None:
    get_streaming_egress_pool().reset_for_tests()


def test_proxy_service_for_platform_known() -> None:
    assert _proxy_service_for_platform("soundcloud") == "soundcloud"
    assert _proxy_service_for_platform("BANDCAMP") == "bandcamp"
    assert _proxy_service_for_platform("youtube") == "youtube"


def test_proxy_service_for_platform_unknown() -> None:
    assert _proxy_service_for_platform(None) is None
    assert _proxy_service_for_platform("yandex_music") is None
    assert _proxy_service_for_platform("") is None


@pytest.mark.anyio
async def test_download_bytes_skips_pool_for_unknown_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``proxy_service`` ⇒ no pool interaction, plain httpx call."""
    seen_kwargs: dict[str, object] = {}

    class _FakeResponse:
        content = b"x" * 16
        headers = {"content-type": "audio/mpeg"}

        def raise_for_status(self) -> None:
            return None

    class _FakeClient:
        def __init__(self, **kwargs: object) -> None:
            seen_kwargs.update(kwargs)

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, url: str) -> _FakeResponse:
            return _FakeResponse()

    monkeypatch.setattr(audio_cache_worker.httpx, "AsyncClient", _FakeClient)
    pool = get_streaming_egress_pool()
    pick_calls: list[object] = []
    monkeypatch.setattr(
        pool, "pick", lambda **kw: pick_calls.append(kw) or None
    )

    data, ct = await _download_bytes(
        "https://example.com/x.mp3",
        proxy_service=None,
        sticky_key=None,
    )

    assert data == b"x" * 16
    assert ct == "audio/mpeg"
    assert seen_kwargs.get("proxy") is None
    assert pick_calls == []


@pytest.mark.anyio
async def test_download_bytes_uses_pool_for_audio_cdn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SoundCloud / Bandcamp downloads pick + finish on the pool."""
    pool = get_streaming_egress_pool()

    decision = StreamingEgressDecision(
        proxy_url="http://proxy.local:1080",
        egress_name="http://proxy.local:1080",
        sticky_key="track:1",
    )
    monkeypatch.setattr(pool, "pick", lambda **_: decision)
    finish_calls: list[bool] = []

    def _finish(d: StreamingEgressDecision, *, ok: bool) -> None:
        finish_calls.append(ok)

    monkeypatch.setattr(pool, "finish", _finish)

    seen_kwargs: dict[str, object] = {}

    class _FakeResponse:
        content = b"y" * 32
        headers = {"content-type": "audio/mp3"}

        def raise_for_status(self) -> None:
            return None

    class _FakeClient:
        def __init__(self, **kwargs: object) -> None:
            seen_kwargs.update(kwargs)

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, url: str) -> _FakeResponse:
            return _FakeResponse()

    monkeypatch.setattr(audio_cache_worker.httpx, "AsyncClient", _FakeClient)

    data, _ = await _download_bytes(
        "https://cf-media.sndcdn.com/media/abc/file.mp3",
        proxy_service="soundcloud",
        sticky_key="track:1:abc",
    )

    assert data == b"y" * 32
    assert seen_kwargs.get("proxy") == "http://proxy.local:1080"
    assert finish_calls == [True]


@pytest.mark.anyio
async def test_download_bytes_releases_pool_slot_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = get_streaming_egress_pool()
    decision = StreamingEgressDecision(
        proxy_url=None,
        egress_name="direct",
        sticky_key="track:1",
    )
    monkeypatch.setattr(pool, "pick", lambda **_: decision)
    finish_calls: list[bool] = []
    monkeypatch.setattr(
        pool,
        "finish",
        lambda d, ok: finish_calls.append(ok),
    )

    class _RaisingClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _RaisingClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, url: str) -> object:
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(
        audio_cache_worker.httpx, "AsyncClient", _RaisingClient
    )

    with pytest.raises(httpx.ConnectError):
        await _download_bytes(
            "https://cf-media.sndcdn.com/media/abc.mp3",
            proxy_service="soundcloud",
            sticky_key="track:1:abc",
        )
    assert finish_calls == [False]


@pytest.mark.anyio
async def test_download_bytes_raises_when_pool_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = get_streaming_egress_pool()
    monkeypatch.setattr(pool, "pick", lambda **_: None)

    with patch(
        "app.core.observability.streaming_egress_pool_exhausted"
    ) as mock_metric:
        with pytest.raises(RuntimeError, match="exhausted"):
            await _download_bytes(
                "https://cf-media.sndcdn.com/media/abc.mp3",
                proxy_service="soundcloud",
                sticky_key="track:1:abc",
            )
        mock_metric.assert_called_once_with(service="soundcloud")
