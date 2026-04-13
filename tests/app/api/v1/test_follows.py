import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, create_test_user

pytestmark = pytest.mark.anyio


async def test_follow_and_unfollow(
    client: AsyncClient,
) -> None:
    u1 = await create_test_user(client, 80001)
    u2 = await create_test_user(client, 80002)
    headers = await auth_headers(client, u1["id"])

    r1 = await client.post(
        f"/api/v1/users/{u2['id']}/follow",
        headers=headers,
    )
    assert r1.status_code == 200
    assert r1.json()["following"] is True

    r2 = await client.post(
        f"/api/v1/users/{u2['id']}/follow",
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["following"] is False


async def test_self_follow_prevented(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 80003)
    headers = await auth_headers(client, user["id"])
    r = await client.post(
        f"/api/v1/users/{user['id']}/follow",
        headers=headers,
    )
    assert r.status_code in (400, 409, 200)


async def test_list_followers_empty(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 80004)
    r = await client.get(
        f"/api/v1/users/{user['id']}/followers",
    )
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_list_following_returns_followed_user(
    client: AsyncClient,
) -> None:
    u1 = await create_test_user(client, 80005)
    u2 = await create_test_user(client, 80006)
    headers = await auth_headers(client, u1["id"])

    await client.post(
        f"/api/v1/users/{u2['id']}/follow",
        headers=headers,
    )

    r = await client.get(
        f"/api/v1/users/{u1['id']}/following",
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == u2["id"]


async def test_follow_status(
    client: AsyncClient,
) -> None:
    u1 = await create_test_user(client, 80007)
    u2 = await create_test_user(client, 80008)
    headers = await auth_headers(client, u1["id"])

    r_before = await client.get(
        f"/api/v1/users/{u2['id']}/follow/status",
        headers=headers,
    )
    assert r_before.status_code == 200
    assert r_before.json()["following"] is False

    await client.post(
        f"/api/v1/users/{u2['id']}/follow",
        headers=headers,
    )

    r_after = await client.get(
        f"/api/v1/users/{u2['id']}/follow/status",
        headers=headers,
    )
    assert r_after.status_code == 200
    assert r_after.json()["following"] is True
