import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def _quick_track(
    client: AsyncClient,
    user_id: int,
) -> int:
    headers = await auth_headers(client, user_id)
    r = await client.get(
        "/api/v1/tracks/?size=1", headers=headers
    )
    return 1


async def test_record_listen_unauthenticated(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/signals/listen",
        json={
            "track_id": 1,
            "duration_listened": 100,
        },
    )
    assert r.status_code == 401


async def test_record_listen(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 9001)
    headers = await auth_headers(client, 9001)

    r = await client.post(
        "/api/v1/signals/listen",
        json={
            "track_id": 1,
            "duration_listened": 120,
            "total_duration": 200,
            "source_context": "home",
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_record_search(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 9002)
    headers = await auth_headers(client, 9002)

    r = await client.post(
        "/api/v1/signals/search",
        json={
            "query": "drake",
            "results_count": 5,
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_record_listen_invalid(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 9003)
    headers = await auth_headers(client, 9003)

    r = await client.post(
        "/api/v1/signals/listen",
        json={
            "track_id": 1,
            "duration_listened": -1,
        },
        headers=headers,
    )
    assert r.status_code == 422
