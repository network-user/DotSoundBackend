import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_home_unauthenticated(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/recommendations/home"
    )
    assert r.status_code == 401


async def test_home_empty(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7001)
    headers = await auth_headers(client, 7001)

    r = await client.get(
        "/api/v1/recommendations/home",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "sections" in data
    assert "maturity" in data


async def test_home_returns_sections(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7002)
    headers = await auth_headers(client, 7002)

    r = await client.get(
        "/api/v1/recommendations/home",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["sections"], list)
    assert data["maturity"] in [
        "cold",
        "warm",
        "calibrated",
        "enriched",
        "personalized",
    ]


async def test_similar_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/recommendations/similar/99999"
    )
    assert r.status_code == 200
    assert r.json()["tracks"] == []


async def test_daily_mix(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7004)
    headers = await auth_headers(client, 7004)

    r = await client.get(
        "/api/v1/recommendations/daily-mix",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "tracks" in data
    assert "generated_at" in data


async def test_radio_missing_seed(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7005)
    headers = await auth_headers(client, 7005)

    r = await client.get(
        "/api/v1/recommendations/radio",
        headers=headers,
    )
    assert r.status_code == 422
