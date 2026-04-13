import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_get_genres_empty(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/metadata/genres")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_get_genres_respects_limit(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/metadata/genres",
        params={"limit": 5},
    )
    assert r.status_code == 200
    assert len(r.json()) <= 5


async def test_get_genres_rejects_bad_limit(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/metadata/genres",
        params={"limit": 0},
    )
    assert r.status_code == 422
