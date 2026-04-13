import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_block_user(
    client: AsyncClient,
) -> None:
    u1 = await create_test_user(
        client, 300001, first_name="A"
    )
    u2 = await create_test_user(
        client, 300002, first_name="B"
    )
    headers = await auth_headers(
        client, u1["id"]
    )

    r = await client.post(
        f"/api/v1/users/{u2['id']}/block",
        headers=headers,
    )
    assert r.status_code == 200

    r = await client.get(
        "/api/v1/blocks",
        headers=headers,
    )
    assert r.status_code == 200
    assert (
        u2["id"] in r.json()["blocked_user_ids"]
    )


async def test_cannot_self_block(
    client: AsyncClient,
) -> None:
    u1 = await create_test_user(
        client, 300003, first_name="C"
    )
    headers = await auth_headers(
        client, u1["id"]
    )

    r = await client.post(
        f"/api/v1/users/{u1['id']}/block",
        headers=headers,
    )
    assert r.status_code == 400


async def test_blocked_user_cannot_create_dm(
    client: AsyncClient,
) -> None:
    u1 = await create_test_user(
        client, 300004, first_name="D"
    )
    u2 = await create_test_user(
        client, 300005, first_name="E"
    )
    headers_u1 = await auth_headers(
        client, u1["id"]
    )
    headers_u2 = await auth_headers(
        client, u2["id"]
    )

    await client.post(
        f"/api/v1/users/{u2['id']}/block",
        headers=headers_u1,
    )

    r = await client.post(
        "/api/v1/chats",
        json={"target_user_id": u1["id"]},
        headers=headers_u2,
    )
    assert r.status_code == 403


async def test_unblock_user(
    client: AsyncClient,
) -> None:
    u1 = await create_test_user(
        client, 300006, first_name="F"
    )
    u2 = await create_test_user(
        client, 300007, first_name="G"
    )
    headers = await auth_headers(
        client, u1["id"]
    )

    await client.post(
        f"/api/v1/users/{u2['id']}/block",
        headers=headers,
    )
    r = await client.delete(
        f"/api/v1/users/{u2['id']}/block",
        headers=headers,
    )
    assert r.status_code == 200

    r = await client.get(
        "/api/v1/blocks",
        headers=headers,
    )
    assert (
        u2["id"]
        not in r.json()["blocked_user_ids"]
    )
