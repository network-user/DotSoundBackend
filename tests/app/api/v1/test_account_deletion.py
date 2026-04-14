import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_delete_account_success(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 80001)
    headers = await auth_headers(
        client, user["id"]
    )
    r = await client.request(
        "DELETE",
        "/api/v1/users/me",
        headers=headers,
        json={"confirmation": "DELETE"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "deletion_scheduled"


async def test_delete_account_wrong_confirmation(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 80002)
    headers = await auth_headers(
        client, user["id"]
    )
    r = await client.request(
        "DELETE",
        "/api/v1/users/me",
        headers=headers,
        json={"confirmation": "wrong"},
    )
    assert r.status_code == 400


async def test_restore_account(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 80003)
    headers = await auth_headers(
        client, user["id"]
    )
    await client.request(
        "DELETE",
        "/api/v1/users/me",
        headers=headers,
        json={"confirmation": "DELETE"},
    )

    r = await client.post(
        "/api/v1/users/me/restore",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is True


async def test_restore_without_deletion(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 80004)
    headers = await auth_headers(
        client, user["id"]
    )
    r = await client.post(
        "/api/v1/users/me/restore",
        headers=headers,
    )
    assert r.status_code == 400
