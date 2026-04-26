
import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, create_test_user

pytestmark = pytest.mark.anyio


async def test_link_status_returns_current_state(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50001)
    headers = await auth_headers(client, user["id"])
    r = await client.get(
        "/api/v1/account/link-status",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["telegram_linked"] is True
    assert data["email_linked"] is False


async def test_link_status_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/account/link-status",
    )
    assert r.status_code == 401


async def test_link_email_rejects_invalid_email(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50002)
    headers = await auth_headers(client, user["id"])
    r = await client.post(
        "/api/v1/account/link/email",
        json={"email": "bad"},
        headers=headers,
    )
    assert r.status_code == 422


async def test_merge_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/account/merge",
        json={"source_account_token": "tok"},
    )
    assert r.status_code == 401
