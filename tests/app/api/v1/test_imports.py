from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, create_test_user

pytestmark = pytest.mark.anyio


async def test_scan_telegram_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.post("/api/v1/import/telegram")
    assert r.status_code == 401


async def test_get_import_status_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/import/1/status")
    assert r.status_code == 401


async def test_get_active_import_none(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 90001)
    headers = await auth_headers(client, user["id"])
    with patch(
        "app.services.import_service"
        ".ImportService.get_active_job",
        new_callable=AsyncMock,
        return_value=None,
    ):
        r = await client.get(
            "/api/v1/import/active",
            headers=headers,
        )
    assert r.status_code == 200
    assert r.json() is None


async def test_cancel_import_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/import/1/cancel",
    )
    assert r.status_code == 401


async def test_scan_yandex_music_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/import/yandex_music",
        json={
            "url": "https://music.yandex.ru/album/1",
        },
    )
    assert r.status_code == 401


async def test_scan_yandex_music_rejects_non_yandex_url(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 90002)
    headers = await auth_headers(client, user["id"])
    r = await client.post(
        "/api/v1/import/yandex_music",
        headers=headers,
        json={"url": "https://example.com/playlist/1"},
    )
    assert r.status_code == 400


async def test_scan_vk_music_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/import/vk_music",
        json={
            "url": "https://vk.com/music/playlist/1/2/3",
        },
    )
    assert r.status_code == 401


async def test_scan_vk_music_rejects_non_vk_url(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 90003)
    headers = await auth_headers(client, user["id"])
    r = await client.post(
        "/api/v1/import/vk_music",
        headers=headers,
        json={"url": "https://example.com/vk.com-fake"},
    )
    assert r.status_code == 400


async def test_scan_vk_passes_normalized_url_to_service(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 90004)
    headers = await auth_headers(client, user["id"])
    with patch(
        "app.api.v1.imports.ImportService.scan_external_playlist",
        new_callable=AsyncMock,
    ) as mock_scan:
        mock_scan.return_value = SimpleNamespace(
            id=1,
            user_id=user["id"],
            source="vk_music",
            status="ready",
            total_tracks=0,
            completed_tracks=0,
            failed_tracks=0,
            tracks_data={},
        )
        r = await client.post(
            "/api/v1/import/vk_music",
            headers=headers,
            json={"url": "https://vk.com/audios-123?z=1"},
        )
    assert r.status_code == 200
    mock_scan.assert_called_once()
    k = mock_scan.call_args.kwargs
    assert k["source"] == "vk_music"
    assert k["url"] == "https://vk.com/audios-123"


async def test_scan_vk_album_url_accepted(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 90005)
    headers = await auth_headers(client, user["id"])
    album = (
        "https://vk.com/music/album/-2000341563_"
        "24341563_5488eb82b4c6a1e448"
    )
    with patch(
        "app.api.v1.imports.ImportService.scan_external_playlist",
        new_callable=AsyncMock,
    ) as mock_scan:
        mock_scan.return_value = SimpleNamespace(
            id=1,
            user_id=user["id"],
            source="vk_music",
            status="ready",
            total_tracks=0,
            completed_tracks=0,
            failed_tracks=0,
            tracks_data={},
        )
        r = await client.post(
            "/api/v1/import/vk_music",
            headers=headers,
            json={"url": album},
        )
    assert r.status_code == 200
    assert mock_scan.call_args.kwargs["url"] == album.rstrip("/")


async def test_scan_soundcloud_playlist_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/import/soundcloud_playlist",
        json={
            "url": "https://soundcloud.com/x/sets/y",
        },
    )
    assert r.status_code == 401


async def test_scan_soundcloud_rejects_non_playlist_url(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 90010)
    headers = await auth_headers(client, user["id"])
    r = await client.post(
        "/api/v1/import/soundcloud_playlist",
        headers=headers,
        json={"url": "https://soundcloud.com/artist/track"},
    )
    assert r.status_code == 400


async def test_scan_soundcloud_passes_to_service(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 90011)
    headers = await auth_headers(client, user["id"])
    url = "https://soundcloud.com/u/sets/mix"
    with patch(
        "app.api.v1.imports.ImportService.scan_external_playlist",
        new_callable=AsyncMock,
    ) as mock_scan:
        mock_scan.return_value = SimpleNamespace(
            id=1,
            user_id=user["id"],
            source="soundcloud_playlist",
            status="ready",
            total_tracks=0,
            completed_tracks=0,
            failed_tracks=0,
            tracks_data={},
        )
        r = await client.post(
            "/api/v1/import/soundcloud_playlist",
            headers=headers,
            json={"url": url},
        )
    assert r.status_code == 200
    k = mock_scan.call_args.kwargs
    assert k["source"] == "soundcloud_playlist"
    assert k["url"] == url


async def test_scan_soundcloud_uses_resolved_on_short_url(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 90014)
    headers = await auth_headers(
        client, user["id"]
    )
    resolved = "https://soundcloud.com/artist/sets/playlist-1"
    with (
        patch(
            "app.api.v1.imports.resolve_public_soundcloud_playlist_url",
            new_callable=AsyncMock,
            return_value=resolved,
        ) as m_res,
        patch(
            "app.api.v1.imports.ImportService.scan_external_playlist",
            new_callable=AsyncMock,
        ) as mock_scan,
    ):
        mock_scan.return_value = SimpleNamespace(
            id=1,
            user_id=user["id"],
            source="soundcloud_playlist",
            status="ready",
            total_tracks=0,
            completed_tracks=0,
            failed_tracks=0,
            tracks_data={},
        )
        r = await client.post(
            "/api/v1/import/soundcloud_playlist",
            headers=headers,
            json={"url": "https://on.soundcloud.com/abc12"},
        )
    assert r.status_code == 200
    m_res.assert_awaited()
    k = mock_scan.call_args.kwargs
    assert k["url"] == resolved


async def test_scan_spotify_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/import/spotify",
        json={"url": "https://open.spotify.com/playlist/abc123"},
    )
    assert r.status_code == 401


async def test_scan_spotify_rejects_non_spotify_url(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 90012)
    headers = await auth_headers(client, user["id"])
    r = await client.post(
        "/api/v1/import/spotify",
        headers=headers,
        json={"url": "https://example.com/playlist/1"},
    )
    assert r.status_code == 400


async def test_scan_spotify_passes_to_service(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 90013)
    headers = await auth_headers(client, user["id"])
    pl = "https://open.spotify.com/playlist/3abcdef"
    with patch(
        "app.api.v1.imports.ImportService.scan_external_playlist",
        new_callable=AsyncMock,
    ) as mock_scan:
        mock_scan.return_value = SimpleNamespace(
            id=1,
            user_id=user["id"],
            source="spotify",
            status="ready",
            total_tracks=0,
            completed_tracks=0,
            failed_tracks=0,
            tracks_data={},
        )
        r = await client.post(
            "/api/v1/import/spotify",
            headers=headers,
            json={"url": pl},
        )
    assert r.status_code == 200
    k = mock_scan.call_args.kwargs
    assert k["source"] == "spotify"
    assert k["url"] == pl


async def test_scan_vk_ru_audio_playlist_url_passes_normalized_z(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 90014)
    headers = await auth_headers(client, user["id"])
    raw = (
        "https://vk.ru/audio?z=audio_playlist156017776_7/"
        "0329b9c56430511e78"
    )
    with patch(
        "app.api.v1.imports.ImportService.scan_external_playlist",
        new_callable=AsyncMock,
    ) as mock_scan:
        mock_scan.return_value = SimpleNamespace(
            id=1,
            user_id=user["id"],
            source="vk_music",
            status="ready",
            total_tracks=0,
            completed_tracks=0,
            failed_tracks=0,
            tracks_data={},
        )
        r = await client.post(
            "/api/v1/import/vk_music",
            headers=headers,
            json={"url": raw},
        )
    assert r.status_code == 200
    k = mock_scan.call_args.kwargs
    assert k["source"] == "vk_music"
    passed = k["url"]
    assert "z=" in passed
    assert "audio_playlist" in passed
