import contextlib
from collections.abc import AsyncIterator, Iterator
from unittest import mock
from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch,
)

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist
from app.services.soundcloud_service import (
    SoundCloudRateLimitError,
    SoundCloudService,
    extract_soundcloud_profile_permalink_from_url,
    normalize_soundcloud_permalink,
    synthetic_soundcloud_id_for_artist_station,
)


@contextlib.asynccontextmanager
async def _noop_slot(*_args: object, **_kwargs: object) -> AsyncIterator[None]:
    yield


async def _noop_get_cached_stream(*_args: object, **_kwargs: object) -> None:
    return None


async def _noop_set_cached_stream(*_args: object, **_kwargs: object) -> None:
    return None


pytestmark = pytest.mark.anyio

_MOD = "app.services.soundcloud_service"


@pytest.fixture(autouse=True)
def _isolate_soundcloud_service(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    from app.services import soundcloud_service

    soundcloud_service._sc_http_client_cache.clear()
    monkeypatch.setattr(soundcloud_service, "soundcloud_slot", _noop_slot)
    monkeypatch.setattr(
        soundcloud_service,
        "get_cached_stream",
        _noop_get_cached_stream,
    )
    monkeypatch.setattr(
        soundcloud_service,
        "set_cached_stream",
        _noop_set_cached_stream,
    )
    yield
    soundcloud_service._sc_http_client_cache.clear()


async def test_search_no_client_id(
    session: AsyncSession,
) -> None:
    svc = SoundCloudService("", session)

    with pytest.raises(HTTPException) as exc:
        await svc.search("test")

    assert exc.value.status_code == 503


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_search_success(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "collection": [
            {
                "kind": "track",
                "streamable": True,
                "title": "Song",
            },
            {
                "kind": "playlist",
                "streamable": True,
            },
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    tracks = await svc.search("test")

    assert len(tracks) == 1
    assert tracks[0]["title"] == "Song"


async def test_search_best_match_raises_when_every_search_fails(
    session: AsyncSession,
) -> None:
    svc = SoundCloudService("test_id", session)
    with (
        patch.object(
            SoundCloudService,
            "search",
            new=AsyncMock(
                side_effect=HTTPException(
                    status_code=503,
                    detail={"code": "soundcloud_client_auth_failed"},
                )
            ),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await svc.search_best_match(
            title="Broken",
            artist="Artist",
        )

    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "soundcloud_client_auth_failed"


async def test_search_best_match_converts_rate_limit_when_all_fail(
    session: AsyncSession,
) -> None:
    svc = SoundCloudService("test_id", session)
    with (
        patch.object(
            SoundCloudService,
            "search",
            new=AsyncMock(
                side_effect=SoundCloudRateLimitError(
                    429,
                    retry_after=3.0,
                )
            ),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await svc.search_best_match(
            title="Broken",
            artist="Artist",
        )

    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "soundcloud_search_unavailable"
    assert exc.value.detail["upstream_status"] == 429
    assert exc.value.detail["retry_after"] == 3.0


async def test_resolve_url_no_client_id(
    session: AsyncSession,
) -> None:
    svc = SoundCloudService("", session)

    with pytest.raises(HTTPException) as exc:
        await svc.resolve_url("https://soundcloud.com/x")

    assert exc.value.status_code == 503


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_resolve_url_not_found(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.resolve_url("https://soundcloud.com/x/y")

    assert exc.value.status_code == 404


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_search_401_expired_key(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.search("test")

    assert exc.value.status_code == 503


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_resolve_url_expired_key(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.resolve_url("https://sc.com/x")

    assert exc.value.status_code == 503


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_resolve_url_success(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "id": 123,
        "title": "Track",
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    result = await svc.resolve_url("https://sc.com/x")

    assert result["title"] == "Track"


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_stream_info_no_transcoding(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resolve_resp = MagicMock()
    resolve_resp.status_code = 200
    resolve_resp.raise_for_status = MagicMock()
    resolve_resp.json.return_value = {
        "media": {"transcodings": []},
        "track_authorization": "",
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resolve_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.get_stream_info("https://sc.com/no-transcode-empty")

    assert exc.value.status_code == 422


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_stream_info_success(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resolve_resp = MagicMock()
    resolve_resp.status_code = 200
    resolve_resp.raise_for_status = MagicMock()
    resolve_resp.json.return_value = {
        "media": {
            "transcodings": [
                {
                    "url": "https://api/stream",
                    "format": {"protocol": "progressive"},
                    "snipped": False,
                }
            ]
        },
        "track_authorization": "auth",
    }

    stream_resp = MagicMock()
    stream_resp.status_code = 200
    stream_resp.raise_for_status = MagicMock()
    stream_resp.json.return_value = {"url": "https://cdn/audio.mp3"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[resolve_resp, stream_resp])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    url, protocol = await svc.get_stream_info("https://sc.com/x")

    assert url == "https://cdn/audio.mp3"
    assert protocol == "progressive"


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_stream_info_progressive_returns_404(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resolve_resp = MagicMock()
    resolve_resp.status_code = 200
    resolve_resp.raise_for_status = MagicMock()
    resolve_resp.json.return_value = {
        "media": {
            "transcodings": [
                {
                    "url": "https://api/stream",
                    "format": {"protocol": "progressive"},
                    "snipped": False,
                }
            ]
        },
        "track_authorization": "auth",
    }

    prog_404 = MagicMock()
    prog_404.status_code = 404

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[resolve_resp, prog_404])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.get_stream_info("https://sc.com/x-prog-404-only")

    assert exc.value.status_code == 502
    detail = _assert_sc_stream_unavailable_detail(exc.value.detail)
    assert detail["attempted_protocols"] == ["progressive"]


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_stream_info_progressive_404_falls_back_to_hls(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resolve_resp = MagicMock()
    resolve_resp.status_code = 200
    resolve_resp.raise_for_status = MagicMock()
    resolve_resp.json.return_value = {
        "media": {
            "transcodings": [
                {
                    "url": "https://api/prog",
                    "format": {"protocol": "progressive"},
                    "snipped": False,
                },
                {
                    "url": "https://api/hls",
                    "format": {"protocol": "hls"},
                    "snipped": False,
                },
            ]
        },
        "track_authorization": "auth",
    }

    prog_404 = MagicMock()
    prog_404.status_code = 404
    hls_ok = MagicMock()
    hls_ok.status_code = 200
    hls_ok.is_success = True
    hls_ok.json.return_value = {"url": "https://cdn/playlist.m3u8"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[resolve_resp, prog_404, hls_ok],
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    url, protocol = await svc.get_stream_info("https://sc.com/fallback-hls")

    assert url == "https://cdn/playlist.m3u8"
    assert protocol == "hls"


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_stream_url(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resolve_resp = MagicMock()
    resolve_resp.status_code = 200
    resolve_resp.raise_for_status = MagicMock()
    resolve_resp.json.return_value = {
        "media": {
            "transcodings": [
                {
                    "url": "https://api/s",
                    "format": {"protocol": "progressive"},
                }
            ]
        },
        "track_authorization": "",
    }

    stream_resp = MagicMock()
    stream_resp.status_code = 200
    stream_resp.raise_for_status = MagicMock()
    stream_resp.json.return_value = {"url": "https://cdn/audio.mp3"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[resolve_resp, stream_resp])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    url = await svc.get_stream_url("https://sc.com/y-get-stream-url")

    assert url == "https://cdn/audio.mp3"


def _make_resp(status_code: int, json_body: dict | None = None) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.is_success = 200 <= status_code < 300
    r.raise_for_status = MagicMock()
    if json_body is not None:
        r.json.return_value = json_body
    return r


def _two_transcodings_payload() -> dict:
    return {
        "media": {
            "transcodings": [
                {
                    "url": "https://api/prog",
                    "format": {"protocol": "progressive"},
                    "snipped": False,
                },
                {
                    "url": "https://api/hls",
                    "format": {"protocol": "hls"},
                    "snipped": False,
                },
            ]
        },
        "track_authorization": "auth",
    }


def _assert_sc_stream_unavailable_detail(
    detail: object,
) -> dict[str, object]:
    assert isinstance(detail, dict)
    assert detail["code"] == "soundcloud_stream_unavailable"
    assert detail["message"] == "SoundCloud stream unavailable"
    assert (
        detail["reason"]
        == "provider_manifest_not_found_for_all_formats"
    )
    assert detail["stage"] == "transcoding_manifest"
    assert detail["upstream_status"] == 404
    return detail


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_stream_info_tries_next_same_protocol_transcoding(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resolve_resp = _make_resp(
        200,
        {
            "media": {
                "transcodings": [
                    {
                        "url": "https://api/hls-old",
                        "format": {"protocol": "hls"},
                        "snipped": False,
                    },
                    {
                        "url": "https://api/hls-fresh",
                        "format": {"protocol": "hls"},
                        "snipped": False,
                    },
                    {
                        "url": "https://api/prog",
                        "format": {"protocol": "progressive"},
                        "snipped": False,
                    },
                ]
            },
            "track_authorization": "auth",
        },
    )
    hls_old_404 = _make_resp(404)
    hls_fresh_ok = _make_resp(
        200,
        {"url": "https://cdn/fresh.m3u8"},
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[resolve_resp, hls_old_404, hls_fresh_ok],
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    url, protocol = await svc.get_stream_info(
        "https://sc.com/multi-hls",
        prefer_hls=True,
    )

    assert url == "https://cdn/fresh.m3u8"
    assert protocol == "hls"
    assert mock_client.get.await_count == 3
    assert mock_client.get.await_args_list[1].args[0] == (
        "https://api/hls-old"
    )
    assert mock_client.get.await_args_list[2].args[0] == (
        "https://api/hls-fresh"
    )


@patch(f"{_MOD}.set_cached_stream", _noop_set_cached_stream)
@patch(f"{_MOD}.get_cached_stream", _noop_get_cached_stream)
@patch(f"{_MOD}.soundcloud_slot", _noop_slot)
@patch(f"{_MOD}.httpx.AsyncClient")
@patch("app.services.outbound_proxy.get_outbound_proxy")
async def test_get_stream_info_all_404_with_tor_retries_direct_succeeds(
    mock_proxy: MagicMock,
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_proxy.return_value = "socks5://127.0.0.1:9050"

    resolve_resp = _make_resp(200, _two_transcodings_payload())
    prog_404 = _make_resp(404)
    hls_404 = _make_resp(404)
    prog_ok = _make_resp(200, {"url": "https://cdn/audio.mp3"})

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[resolve_resp, prog_404, hls_404, prog_ok],
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    with (
        patch(
            f"{_MOD}.settings.sc_stream_fallback_direct_on_tor_failure",
            True,
        ),
        patch(
            f"{_MOD}.settings.sc_stream_manifest_proxy_retries",
            0,
        ),
        patch(
            "app.services.outbound_proxy.outbound_proxy_configured",
            return_value=True,
        ),
    ):
        url, protocol = await svc.get_stream_info(
            "https://sc.com/x-tor-retry-direct",
        )

    assert url == "https://cdn/audio.mp3"
    assert protocol == "progressive"

    proxies_used = [
        c.kwargs.get("proxy") for c in mock_client_cls.call_args_list
    ]
    assert "socks5://127.0.0.1:9050" in proxies_used
    assert None in proxies_used


@patch(f"{_MOD}.set_cached_stream", _noop_set_cached_stream)
@patch(f"{_MOD}.get_cached_stream", _noop_get_cached_stream)
@patch(f"{_MOD}.soundcloud_slot", _noop_slot)
@patch(f"{_MOD}.httpx.AsyncClient")
@patch("app.services.outbound_proxy.get_outbound_proxy")
async def test_get_stream_info_all_404_retries_proxy_before_direct(
    mock_proxy: MagicMock,
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_proxy.side_effect = [
        "socks5://127.0.0.1:9150",
        "socks5://127.0.0.1:9151",
        "socks5://127.0.0.1:9152",
    ]

    resolve_resp = _make_resp(200, _two_transcodings_payload())
    prog_404 = _make_resp(404)
    hls_404 = _make_resp(404)
    prog_ok = _make_resp(200, {"url": "https://cdn/audio.mp3"})

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[resolve_resp, prog_404, hls_404, prog_ok],
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    with (
        patch(f"{_MOD}.settings.sc_stream_manifest_proxy_retries", 1),
        patch(
            f"{_MOD}.settings.sc_stream_fallback_direct_on_tor_failure",
            False,
        ),
        patch(
            "app.services.outbound_proxy.outbound_proxy_configured",
            return_value=True,
        ),
        patch(
            "app.services.outbound_proxy.report_outbound_proxy_result",
        ) as report_proxy_result,
    ):
        url, protocol = await svc.get_stream_info(
            "https://sc.com/x-proxy-retry",
        )

    assert url == "https://cdn/audio.mp3"
    assert protocol == "progressive"
    proxies_used = [
        c.kwargs.get("proxy") for c in mock_client_cls.call_args_list
    ]
    assert "socks5://127.0.0.1:9152" in proxies_used
    assert None not in proxies_used
    report_proxy_result.assert_any_call(
        "socks5://127.0.0.1:9151",
        ok=False,
    )
    report_proxy_result.assert_any_call(
        "socks5://127.0.0.1:9152",
        ok=True,
    )


@patch(f"{_MOD}.set_cached_stream", _noop_set_cached_stream)
@patch(f"{_MOD}.get_cached_stream", _noop_get_cached_stream)
@patch(f"{_MOD}.soundcloud_slot", _noop_slot)
@patch(f"{_MOD}.httpx.AsyncClient")
@patch("app.services.outbound_proxy.get_outbound_proxy")
async def test_get_stream_info_all_404_with_tor_retry_direct_also_fails(
    mock_proxy: MagicMock,
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_proxy.return_value = "socks5://127.0.0.1:9050"

    resolve_resp = _make_resp(200, _two_transcodings_payload())
    prog_404 = _make_resp(404)
    hls_404 = _make_resp(404)
    prog_404_direct = _make_resp(404)
    hls_404_direct = _make_resp(404)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[
            resolve_resp,
            prog_404,
            hls_404,
            prog_404_direct,
            hls_404_direct,
        ],
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with (
        patch(
            f"{_MOD}.settings.sc_stream_fallback_direct_on_tor_failure",
            True,
        ),
        patch(
            f"{_MOD}.settings.sc_stream_manifest_proxy_retries",
            0,
        ),
        patch(
            "app.services.outbound_proxy.outbound_proxy_configured",
            return_value=True,
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await svc.get_stream_info("https://sc.com/x-tor-retry-direct-fails")

    assert exc.value.status_code == 502
    detail = _assert_sc_stream_unavailable_detail(exc.value.detail)
    assert detail["direct_fallback_attempted"] is True
    assert detail["direct_fallback_outcome"] == "all_404"


@patch(f"{_MOD}.set_cached_stream", _noop_set_cached_stream)
@patch(f"{_MOD}.get_cached_stream", _noop_get_cached_stream)
@patch(f"{_MOD}.soundcloud_slot", _noop_slot)
@patch(f"{_MOD}.httpx.AsyncClient")
@patch("app.services.outbound_proxy.get_outbound_proxy")
async def test_get_stream_info_all_404_no_tor_does_not_retry_direct(
    mock_proxy: MagicMock,
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_proxy.return_value = None

    resolve_resp = _make_resp(200, _two_transcodings_payload())
    prog_404 = _make_resp(404)
    hls_404 = _make_resp(404)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[resolve_resp, prog_404, hls_404],
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.get_stream_info("https://sc.com/x-no-tor-no-retry")

    assert exc.value.status_code == 502
    detail = _assert_sc_stream_unavailable_detail(exc.value.detail)
    assert detail["outbound_configured"] is False
    assert mock_client.get.await_count == 3


@patch(f"{_MOD}.set_cached_stream", _noop_set_cached_stream)
@patch(f"{_MOD}.get_cached_stream", _noop_get_cached_stream)
@patch(f"{_MOD}.soundcloud_slot", _noop_slot)
@patch(f"{_MOD}.httpx.AsyncClient")
@patch("app.services.outbound_proxy.get_outbound_proxy")
async def test_get_stream_info_all_404_with_tor_fallback_flag_off(
    mock_proxy: MagicMock,
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_proxy.return_value = "socks5://127.0.0.1:9050"

    resolve_resp = _make_resp(200, _two_transcodings_payload())
    prog_404 = _make_resp(404)
    hls_404 = _make_resp(404)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[resolve_resp, prog_404, hls_404],
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with (
        patch(
            f"{_MOD}.settings.sc_stream_fallback_direct_on_tor_failure",
            False,
        ),
        patch(
            f"{_MOD}.settings.sc_stream_manifest_proxy_retries",
            0,
        ),
        patch(
            "app.services.outbound_proxy.outbound_proxy_configured",
            return_value=True,
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await svc.get_stream_info("https://sc.com/x-flag-off")

    assert exc.value.status_code == 502
    detail = _assert_sc_stream_unavailable_detail(exc.value.detail)
    assert detail["direct_fallback_enabled"] is False
    assert mock_client.get.await_count == 3


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_charts_no_client_id(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    svc = SoundCloudService("", session)
    result = await svc.get_charts()
    assert result == []


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_charts_success(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "collection": [
            {
                "track": {
                    "id": 1,
                    "title": "Hit",
                    "streamable": True,
                }
            },
            {"track": None},
            {"track": {"id": 2, "streamable": False}},
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    result = await svc.get_charts(genre="rock", limit=10)

    assert len(result) == 1
    assert result[0]["title"] == "Hit"


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_charts_429_raises_rate_limit_error(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "1"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    with pytest.raises(SoundCloudRateLimitError) as exc_info:
        await svc.get_charts()
    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 1.0


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_trending_delegates_to_charts(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"collection": []}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    result = await svc.get_trending(limit=5)
    assert result == []


@patch(
    "app.services.track_ingest_schedule_service"
    ".schedule_new_track_background_jobs",
    new_callable=AsyncMock,
)
async def test_import_or_get_track_sets_provenance(
    _sched: object,
    session: AsyncSession,
) -> None:
    svc = SoundCloudService("test_id", session)
    sc_url = "https://soundcloud.com/test/track"
    track = await svc.import_or_get_track(
        {
            "permalink_url": sc_url,
            "title": "Imported Track",
            "user": {"username": "Artist"},
            "duration": 123000,
            "uri": "sc:track",
        },
        uploader_id=1,
    )

    assert track.source == "soundcloud"
    assert track.catalog_type == "external_reference"
    assert track.access_mode == "third_party_stream"
    assert track.source_platform == "soundcloud"
    assert track.source_url == sc_url
    assert track.canonical_source_url == sc_url
    assert track.source_name == "SoundCloud"


@patch(
    "app.services.track_ingest_schedule_service"
    ".schedule_new_track_background_jobs",
    new_callable=AsyncMock,
)
async def test_import_or_get_track_dedup_via_unique_index(
    _sched: object,
    session: AsyncSession,
) -> None:
    # Importing the same SC URL twice in a row must return the
    # first row, not create a duplicate (the partial unique index
    # on tracks.sc_url + ON CONFLICT DO NOTHING handle the race).
    svc = SoundCloudService("test_id", session)
    sc_url = "https://soundcloud.com/dedup/case"
    sc_data = {
        "permalink_url": sc_url,
        "title": "Same Song",
        "user": {"username": "Artist"},
        "duration": 90000,
        "uri": "sc:dedup",
    }

    first = await svc.import_or_get_track(sc_data, uploader_id=1)
    second = await svc.import_or_get_track(sc_data, uploader_id=2)

    assert first.id == second.id
    assert first.uploaded_by_id == 1


def test_normalize_soundcloud_permalink_slug() -> None:
    assert (
        normalize_soundcloud_permalink(
            "https://soundcloud.com/MyArtist/tracks"
        )
        == "myartist"
    )
    assert normalize_soundcloud_permalink("PlainSlug") == "plainslug"


def test_extract_soundcloud_profile_permalink_from_url() -> None:
    assert (
        extract_soundcloud_profile_permalink_from_url(
            "https://soundcloud.com/DJTest?utm=x"
        )
        == "djtest"
    )
    assert (
        extract_soundcloud_profile_permalink_from_url(
            "https://soundcloud.com/tracks/xyz"
        )
        is None
    )
    assert extract_soundcloud_profile_permalink_from_url("") is None


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_search_users_filters_non_users(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "collection": [
            {"kind": "track", "id": 1},
            {
                "kind": "user",
                "id": 42,
                "permalink": "found",
            },
        ]
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("cid", session)
    users = await svc.search_users("q")

    assert len(users) == 1
    assert users[0]["id"] == 42


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_list_user_albums_pagination(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.raise_for_status = MagicMock()
    resp1.json.return_value = {
        "collection": [{"id": 10, "title": "One"}],
        "next_href": "https://api-v2.soundcloud.com/page2",
    }
    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.raise_for_status = MagicMock()
    resp2.json.return_value = {
        "collection": [{"id": 11, "title": "Two"}],
        "next_href": None,
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[resp1, resp2])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    albums, truncated = await svc.list_user_albums(12345)

    assert len(albums) == 2
    assert albums[0]["id"] == 10
    assert albums[1]["id"] == 11
    assert truncated is False


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_list_user_albums_respects_max_total(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    big = [{"id": i, "title": f"A{i}"} for i in range(5)]
    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.raise_for_status = MagicMock()
    resp1.json.return_value = {
        "collection": big,
        "next_href": "https://api-v2.soundcloud.com/more",
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp1)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    albums, truncated = await svc.list_user_albums(9, max_total=2)

    assert len(albums) == 2
    assert truncated is True
    mock_client.get.assert_awaited_once()


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_fetch_playlist_by_id_ok(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "id": 9001,
        "title": "Pl",
        "user": {"id": 3},
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    pl = await svc.fetch_playlist_by_id(9001)

    assert pl["id"] == 9001
    assert pl["title"] == "Pl"


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_expand_playlist_stub_tracks(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    fetch_resp = MagicMock()
    fetch_resp.status_code = 200
    fetch_resp.raise_for_status = MagicMock()
    fetch_resp.json.return_value = {
        "id": 77,
        "permalink_url": "https://soundcloud.com/u/full",
        "title": "Resolved",
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=fetch_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    result = await svc.expand_playlist_stub_tracks({"tracks": [{"id": 77}]})

    assert result["tracks"][0]["title"] == "Resolved"


async def test_ensure_soundcloud_ids_applies(
    session: AsyncSession,
) -> None:
    artist = Artist(name="Act", name_normalized="act")
    session.add(artist)
    await session.flush()

    svc = SoundCloudService("test_id", session)
    ok = await svc.ensure_soundcloud_ids_for_artist(
        artist.id,
        424242,
        "https://soundcloud.com/scuser/extra",
    )

    assert ok is True
    await session.refresh(artist)
    assert artist.soundcloud_user_id == 424242
    assert artist.soundcloud_permalink == "scuser"


async def test_ensure_soundcloud_ids_idempotent_same_user(
    session: AsyncSession,
) -> None:
    artist = Artist(
        name="Act",
        name_normalized="act2",
        soundcloud_user_id=99,
        soundcloud_permalink="oldslug",
    )
    session.add(artist)
    await session.flush()

    svc = SoundCloudService("test_id", session)
    ok = await svc.ensure_soundcloud_ids_for_artist(
        artist.id,
        99,
        "newslug",
    )

    assert ok is True
    await session.refresh(artist)
    assert artist.soundcloud_permalink == "newslug"


async def test_ensure_soundcloud_ids_skips_on_user_mismatch(
    session: AsyncSession,
) -> None:
    artist = Artist(
        name="Act",
        name_normalized="act3",
        soundcloud_user_id=1,
    )
    session.add(artist)
    await session.flush()

    svc = SoundCloudService("test_id", session)
    ok = await svc.ensure_soundcloud_ids_for_artist(
        artist.id,
        2,
        None,
    )

    assert ok is False
    await session.refresh(artist)
    assert artist.soundcloud_user_id == 1


@patch(
    f"{_MOD}.s3.upload_image",
    new_callable=AsyncMock,
    return_value=(
        "artists/1/abc.webp",
        "artists/1/abc_thumb.webp",
        64,
        64,
    ),
)
@patch(f"{_MOD}.httpx.AsyncClient")
async def test_sync_artist_soundcloud_uploader_profile_avatar(
    mock_client_cls: AsyncMock,
    mock_upload_image: AsyncMock,
    session: AsyncSession,
) -> None:
    artist = Artist(name="ScAct", name_normalized="scact")
    session.add(artist)
    await session.flush()

    img_resp = MagicMock()
    img_resp.status_code = 200
    img_resp.content = b"\xff\xd8\xff\xe0"
    img_resp.headers = {"content-type": "image/jpeg"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=img_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    await svc.sync_artist_soundcloud_uploader_profile(
        artist.id,
        {
            "id": 90001,
            "permalink": "scactslug",
            "avatar_url": "https://i1.sndcdn.com/avatars-000/large.jpg",
        },
        uploader_id=1,
    )

    await session.refresh(artist)
    assert artist.soundcloud_user_id == 90001
    assert artist.soundcloud_permalink == "scactslug"
    assert artist.image_key == "artists/1/abc.webp"
    mock_upload_image.assert_awaited_once()


@patch(f"{_MOD}.s3.upload_image")
async def test_sync_artist_soundcloud_skips_default_avatar(
    mock_upload_image: AsyncMock,
    session: AsyncSession,
) -> None:
    artist = Artist(name="NoPic", name_normalized="nopic")
    session.add(artist)
    await session.flush()

    svc = SoundCloudService("test_id", session)
    await svc.sync_artist_soundcloud_uploader_profile(
        artist.id,
        {
            "id": 80002,
            "permalink": "nopic",
            "avatar_url": (
                "https://a1.sndcdn.com/images/default_avatar_large.png"
            ),
        },
        uploader_id=1,
    )

    await session.refresh(artist)
    assert artist.soundcloud_user_id == 80002
    assert artist.image_key is None
    mock_upload_image.assert_not_called()


async def test_ensure_soundcloud_ids_skips_when_sc_id_taken(
    session: AsyncSession,
) -> None:
    a1 = Artist(
        name="First",
        name_normalized="first",
        soundcloud_user_id=500,
    )
    a2 = Artist(name="Second", name_normalized="second")
    session.add_all([a1, a2])
    await session.flush()

    svc = SoundCloudService("test_id", session)
    ok = await svc.ensure_soundcloud_ids_for_artist(
        a2.id,
        500,
        None,
    )

    assert ok is False
    await session.refresh(a2)
    assert a2.soundcloud_user_id is None


@mock.patch.object(SoundCloudService, "search_users", new_callable=AsyncMock)
async def test_try_autofill_applies_first_search_hit(
    mock_search: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_search.return_value = [
        {"kind": "user", "id": 777001, "permalink": "uinc"},
    ]
    artist = Artist(
        name="Unique Sc Autofill",
        name_normalized="unique-sc-autofill-xyz",
    )
    session.add(artist)
    await session.flush()

    svc = SoundCloudService("test_id", session)
    ok = await svc.try_autofill_soundcloud_user_id_for_artist(artist.id)

    assert ok is True
    await session.refresh(artist)
    assert artist.soundcloud_user_id == 777001
    assert artist.soundcloud_permalink == "uinc"
    mock_search.assert_awaited()


def test_synthetic_soundcloud_id_for_artist_station() -> None:
    uid = 1023668788
    sid = synthetic_soundcloud_id_for_artist_station(uid)
    assert sid < 0
    assert sid == -(10**15 + uid)


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_fetch_tracks_by_ids_bulk_batches(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    responses: list[MagicMock] = []

    def _make_resp(items: list[dict]) -> MagicMock:
        m = MagicMock()
        m.status_code = 200
        m.raise_for_status = MagicMock()
        m.json.return_value = items
        return m

    ids_a = [{"id": i, "title": f"t{i}"} for i in range(50)]
    ids_b = [{"id": 50, "title": "t50"}]
    responses.append(_make_resp(ids_a))
    responses.append(_make_resp(ids_b))

    mock_client = AsyncMock()

    async def _get(*_a: object, **_k: object) -> MagicMock:
        return responses.pop(0)

    mock_client.get = AsyncMock(side_effect=_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("cid", session)
    out = await svc.fetch_tracks_by_ids_bulk(list(range(51)))

    assert len(out) == 51
    assert mock_client.get.await_count == 2


@patch.object(
    SoundCloudService,
    "resolve_url",
    new_callable=AsyncMock,
)
@patch.object(
    SoundCloudService,
    "fetch_tracks_by_ids_bulk",
    new_callable=AsyncMock,
)
async def test_fetch_expanded_artist_station_playlist(
    mock_bulk: AsyncMock,
    mock_resolve: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_resolve.return_value = {
        "kind": "system-playlist",
        "id": "soundcloud:system-playlists:artist-stations:7",
        "title": "Artist",
        "tracks": [
            {"id": 11, "kind": "track"},
            {"id": 12, "kind": "track"},
        ],
    }
    mock_bulk.return_value = [
        {"id": 11, "title": "A", "permalink_url": "https://sc/a"},
        {"id": 12, "title": "B", "permalink_url": "https://sc/b"},
    ]

    svc = SoundCloudService("cid", session)
    pl = await svc.fetch_expanded_artist_station_playlist(7)

    assert pl["id"] == synthetic_soundcloud_id_for_artist_station(7)
    assert len(pl["tracks"]) == 2
    mock_resolve.assert_awaited_once()
    called_url = mock_resolve.await_args[0][0]
    assert "artist-stations:7" in called_url
    mock_bulk.assert_awaited_once_with([11, 12])
