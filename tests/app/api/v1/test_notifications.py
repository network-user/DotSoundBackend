import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_empty_notifications(
    client: AsyncClient,
) -> None:
    u = await create_test_user(
        client, 500001, first_name="Notif"
    )
    headers = await auth_headers(
        client, u["id"]
    )
    r = await client.get(
        "/api/v1/notifications",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_unread_count_zero(
    client: AsyncClient,
) -> None:
    u = await create_test_user(
        client, 500002, first_name="Count"
    )
    headers = await auth_headers(
        client, u["id"]
    )
    r = await client.get(
        "/api/v1/notifications/unread-count",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["count"] == 0


async def test_mark_all_read(
    client: AsyncClient,
) -> None:
    u = await create_test_user(
        client, 500003, first_name="All"
    )
    headers = await auth_headers(
        client, u["id"]
    )
    r = await client.post(
        "/api/v1/notifications/read-all",
        headers=headers,
    )
    assert r.status_code == 200
