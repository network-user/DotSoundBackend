from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_get_current_user_valid_token(
    client: AsyncClient,
) -> None:
    user_data = await create_test_user(
        client, telegram_id=8001
    )
    headers = await auth_headers(
        client, user_data["id"]
    )

    resp = await client.get(
        "/api/v1/users/me/feed", headers=headers
    )

    assert resp.status_code == 200


async def test_get_current_user_no_credentials(
    client: AsyncClient,
) -> None:
    resp = await client.get(
        "/api/v1/users/me/feed"
    )

    assert resp.status_code == 401


async def test_get_current_user_invalid_token(
    client: AsyncClient,
) -> None:
    headers = {
        "Authorization": "Bearer invalid.jwt.token"
    }

    resp = await client.get(
        "/api/v1/users/me/feed", headers=headers
    )

    assert resp.status_code == 401


async def test_get_optional_user_no_credentials(
    client: AsyncClient,
) -> None:
    resp = await client.get("/api/v1/albums/99999")

    assert resp.status_code in (200, 404)


async def test_require_admin_rejects_user_jwt(
    client: AsyncClient,
) -> None:
    user_data = await create_test_user(
        client, telegram_id=8002
    )
    headers = await auth_headers(
        client, user_data["id"]
    )
    resp = await client.get(
        "/api/v1/admin/tracks", headers=headers
    )
    assert resp.status_code == 401
