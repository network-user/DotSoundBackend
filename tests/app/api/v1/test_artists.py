import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_list_artists_empty(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/artists")
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_get_artist_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/artists/99999")
    assert r.status_code == 404


async def test_artist_tracks_empty(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/artists/99999/tracks"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_similar_artists_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/artists/99999/similar"
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0
