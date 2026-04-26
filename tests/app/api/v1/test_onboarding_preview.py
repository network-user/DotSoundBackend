import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, create_test_user

pytestmark = pytest.mark.anyio


async def test_preview_queue_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/onboarding/genres/Rock/preview-queue",
    )
    assert r.status_code == 401


async def test_preview_queue_ok_empty(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 88001)
    headers = await auth_headers(client, 88001)
    r = await client.get(
        "/api/v1/onboarding/genres/NoSuchGenreXyz/preview-queue"
        "?limit=3",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json() == {"items": []}
