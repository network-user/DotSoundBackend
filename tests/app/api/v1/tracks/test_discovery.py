from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_list_tracks_empty(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/tracks/"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


async def test_list_tracks_pagination(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/tracks/",
        params={"page": 1, "size": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["size"] == 5
    assert isinstance(data["items"], list)


async def test_get_track_not_found(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/tracks/99999"
    )
    assert response.status_code == 404


async def test_cover_proxy_accepts_artist_avatars_prefix(
    client: AsyncClient,
) -> None:
    webp = (
        b"RIFF\x1e\x00\x00\x00WEBPVP8 "
        + b"\x0a\x00\x00\x00\x10\x00\x00\x00\x00\x00"
        + b"\x00\x00\x00\x00\x00"
    )
    with patch(
        "app.api.v1.tracks.discovery.s3.download_object",
        new_callable=AsyncMock,
        return_value=webp,
    ):
        r = await client.get(
            "/api/v1/tracks/cover_proxy",
            params={"key": "artist-avatars/1/sample.webp"},
        )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/")


async def test_search_tracks_empty(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/tracks/",
        params={"q": "nonexistent_xyz"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
