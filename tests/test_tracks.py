import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_tracks_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


@pytest.mark.anyio
async def test_list_tracks_pagination(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/tracks", params={"page": 1, "size": 5}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["size"] == 5
    assert isinstance(data["items"], list)


@pytest.mark.anyio
async def test_get_track_not_found(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/tracks/99999")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_search_tracks_empty(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/tracks", params={"q": "nonexistent_xyz"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
