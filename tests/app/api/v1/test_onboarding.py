import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_status_unauthenticated(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/onboarding/status"
    )
    assert r.status_code == 401


async def test_status_new_user(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 8001)
    headers = await auth_headers(client, 8001)

    r = await client.get(
        "/api/v1/onboarding/status",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["onboarding_completed"] is False
    assert data["calibration_completed"] is False


async def test_get_genres(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/onboarding/genres"
    )
    assert r.status_code == 200
    genres = r.json()
    assert isinstance(genres, list)
    assert len(genres) >= 10


async def test_save_preferences(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 8002)
    headers = await auth_headers(client, 8002)

    r = await client.post(
        "/api/v1/onboarding/preferences",
        json={
            "genres": ["rock", "pop", "jazz"],
            "artist_ids": [],
            "moods": ["chill"],
        },
        headers=headers,
    )
    assert r.status_code == 200

    r2 = await client.get(
        "/api/v1/onboarding/status",
        headers=headers,
    )
    assert r2.json()["onboarding_completed"] is True


async def test_complete(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 8003)
    headers = await auth_headers(client, 8003)

    r = await client.post(
        "/api/v1/onboarding/complete",
        headers=headers,
    )
    assert r.status_code == 200

    r2 = await client.get(
        "/api/v1/onboarding/status",
        headers=headers,
    )
    assert r2.json()["onboarding_completed"] is True
