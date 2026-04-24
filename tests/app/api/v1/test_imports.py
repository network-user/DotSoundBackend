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
