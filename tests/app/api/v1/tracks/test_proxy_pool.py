"""Unit tests for audio-proxy client pool and body_iter penalty logic."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

pytestmark = pytest.mark.anyio


def _clear_pool() -> None:
    from app.api.v1.tracks import playback as mod

    mod._audio_proxy_http_clients.clear()


@pytest.fixture(autouse=True)
def isolate_pool() -> None:
    _clear_pool()
    yield
    _clear_pool()


# ---------------------------------------------------------------------------
# _get_audio_proxy_client — pool behaviour
# ---------------------------------------------------------------------------


def test_get_audio_proxy_client_reuses_same_instance() -> None:
    from app.api.v1.tracks import playback as mod

    c1 = mod._get_audio_proxy_client("socks5://c0:ds@127.0.0.1:9050")
    c2 = mod._get_audio_proxy_client("socks5://c0:ds@127.0.0.1:9050")
    assert c1 is c2


def test_get_audio_proxy_client_distinct_per_proxy() -> None:
    from app.api.v1.tracks import playback as mod

    c1 = mod._get_audio_proxy_client("socks5://c0:ds@127.0.0.1:9050")
    c2 = mod._get_audio_proxy_client("socks5://c1:ds@127.0.0.1:9051")
    assert c1 is not c2


def test_get_audio_proxy_client_none_proxy_is_cached() -> None:
    from app.api.v1.tracks import playback as mod

    c1 = mod._get_audio_proxy_client(None)
    c2 = mod._get_audio_proxy_client(None)
    assert c1 is c2


async def test_get_audio_proxy_client_recreates_after_close() -> None:
    from app.api.v1.tracks import playback as mod

    c1 = mod._get_audio_proxy_client("socks5://c0:ds@127.0.0.1:9050")
    await c1.aclose()
    c2 = mod._get_audio_proxy_client("socks5://c0:ds@127.0.0.1:9050")
    assert c2 is not c1
    assert not c2.is_closed


# ---------------------------------------------------------------------------
# reset_audio_proxy_clients
# ---------------------------------------------------------------------------


def test_reset_audio_proxy_clients_clears_pool() -> None:
    from app.api.v1.tracks import playback as mod

    mod._get_audio_proxy_client("socks5://c0:ds@127.0.0.1:9050")
    assert mod._audio_proxy_http_clients
    mod.reset_audio_proxy_clients()
    assert not mod._audio_proxy_http_clients


def test_reset_audio_proxy_clients_does_not_close_existing() -> None:
    from app.api.v1.tracks import playback as mod

    client = mod._get_audio_proxy_client("socks5://c0:ds@127.0.0.1:9050")
    mod.reset_audio_proxy_clients()
    assert not client.is_closed


# ---------------------------------------------------------------------------
# body_iter — upstream_error penalty logic
# ---------------------------------------------------------------------------


class _CleanResp:
    status_code = 200
    headers: dict[str, str] = {
        "content-type": "audio/mpeg",
        "content-length": "3",
    }

    async def aiter_bytes(self, _: int) -> AsyncIterator[bytes]:
        yield b"abc"

    async def aclose(self) -> None:
        return None


class _ErrorResp:
    status_code = 200
    headers: dict[str, str] = {"content-type": "audio/mpeg"}

    async def aiter_bytes(self, _: int) -> AsyncIterator[bytes]:
        raise httpx.ReadError("connection reset")
        yield b""  # make it a generator

    async def aclose(self) -> None:
        return None


class _MultiChunkResp:
    status_code = 200
    headers: dict[str, str] = {"content-type": "audio/mpeg"}

    async def aiter_bytes(self, _: int) -> AsyncIterator[bytes]:
        yield b"chunk1"
        yield b"chunk2"

    async def aclose(self) -> None:
        return None


def _make_fake_client(resp: object) -> SimpleNamespace:
    return SimpleNamespace(
        build_request=lambda *a, **kw: object(),
        send=AsyncMock(return_value=resp),
        aclose=AsyncMock(),
    )


async def test_body_iter_reports_ok_on_clean_completion() -> None:
    from app.api.v1.tracks import playback as mod
    from app.services.streaming_egress_pool import (
        get_streaming_egress_pool,
    )

    fake_client = _make_fake_client(_CleanResp())
    pool = get_streaming_egress_pool()
    pool.reset_for_tests()

    with (
        patch(
            "app.api.v1.tracks.playback.httpx.AsyncClient",
            return_value=fake_client,
        ),
        patch.object(pool, "finish", wraps=pool.finish) as mock_finish,
    ):
        resp = await mod._http_proxy_range_get(
            SimpleNamespace(headers={}),  # type: ignore[arg-type]
            "https://media.sndcdn.com/x.mp3",
            detail_fail="fail",
            detail_error="error",
            proxy_service="soundcloud",
        )
        body = b""
        async for chunk in resp.body_iterator:
            body += chunk

    assert body == b"abc"
    assert "content-length" not in resp.headers
    mock_finish.assert_called_once()
    finish_kwargs = mock_finish.call_args.kwargs
    assert finish_kwargs["ok"] is True


async def test_body_iter_reports_fail_on_upstream_http_error() -> None:
    from app.api.v1.tracks import playback as mod
    from app.services.streaming_egress_pool import (
        get_streaming_egress_pool,
    )

    fake_client = _make_fake_client(_ErrorResp())
    pool = get_streaming_egress_pool()
    pool.reset_for_tests()

    with (
        patch(
            "app.api.v1.tracks.playback.httpx.AsyncClient",
            return_value=fake_client,
        ),
        patch.object(pool, "finish", wraps=pool.finish) as mock_finish,
    ):
        resp = await mod._http_proxy_range_get(
            SimpleNamespace(headers={}),  # type: ignore[arg-type]
            "https://media.sndcdn.com/x.mp3",
            detail_fail="fail",
            detail_error="error",
            proxy_service="soundcloud",
        )
        async for _ in resp.body_iterator:
            pass

    mock_finish.assert_called_once()
    finish_kwargs = mock_finish.call_args.kwargs
    assert finish_kwargs["ok"] is False


async def test_body_iter_does_not_penalise_on_client_disconnect() -> None:
    """Consumer breaking early must NOT mark the egress as failed."""
    from app.api.v1.tracks import playback as mod
    from app.services.streaming_egress_pool import (
        get_streaming_egress_pool,
    )

    fake_client = _make_fake_client(_MultiChunkResp())
    pool = get_streaming_egress_pool()
    pool.reset_for_tests()

    with (
        patch(
            "app.api.v1.tracks.playback.httpx.AsyncClient",
            return_value=fake_client,
        ),
        patch.object(pool, "finish", wraps=pool.finish) as mock_finish,
    ):
        resp = await mod._http_proxy_range_get(
            SimpleNamespace(headers={}),  # type: ignore[arg-type]
            "https://media.sndcdn.com/x.mp3",
            detail_fail="fail",
            detail_error="error",
            proxy_service="soundcloud",
        )
        gen = resp.body_iterator.__aiter__()
        await gen.__anext__()
        await gen.aclose()

    mock_finish.assert_called_once()
    finish_kwargs = mock_finish.call_args.kwargs
    assert finish_kwargs["ok"] is True


# ---------------------------------------------------------------------------
# _warm_outbound_proxy_pool
# ---------------------------------------------------------------------------


async def test_warm_outbound_proxy_pool_calls_each_proxy() -> None:
    from app.main import _warm_outbound_proxy_pool

    proxy_urls = [
        "socks5h://c0:ds@127.0.0.1:9050",
        "socks5h://c1:ds@127.0.0.1:9051",
    ]

    fake_resp = MagicMock()
    fake_clients: dict[str | None, MagicMock] = {}

    def _fake_get_client(proxy: str | None) -> MagicMock:
        if proxy not in fake_clients:
            fc = MagicMock()
            fc.get = AsyncMock(return_value=fake_resp)
            fake_clients[proxy] = fc
        return fake_clients[proxy]

    class _Cfg:
        outbound_static_proxy_urls_list = proxy_urls

    with (
        patch("app.main.settings", _Cfg()),
        patch(
            "app.api.v1.tracks.playback._get_audio_proxy_client",
            side_effect=_fake_get_client,
        ),
    ):
        await _warm_outbound_proxy_pool()

    assert set(fake_clients) == set(proxy_urls)
    for fc in fake_clients.values():
        fc.get.assert_awaited_once()


async def test_warm_outbound_proxy_pool_skips_when_no_proxies() -> None:
    from app.main import _warm_outbound_proxy_pool

    class _Cfg:
        outbound_static_proxy_urls_list: list[str] = []

    with (
        patch("app.main.settings", _Cfg()),
        patch(
            "app.services.tor_pool.get_tor_pool",
            return_value=None,
        ),
        patch(
            "app.api.v1.tracks.playback._get_audio_proxy_client"
        ) as mock_client,
    ):
        await _warm_outbound_proxy_pool()

    mock_client.assert_not_called()
