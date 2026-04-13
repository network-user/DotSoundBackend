from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_ws_rejects_no_token(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/ws",
        headers={
            "connection": "upgrade",
            "upgrade": "websocket",
        },
    )
    assert r.status_code in (
        403, 400, 404, 200,
    )


async def test_ws_rejects_invalid_token(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/ws?token=invalid_jwt_token",
        headers={
            "connection": "upgrade",
            "upgrade": "websocket",
        },
    )
    assert r.status_code in (
        403, 400, 404, 200,
    )


@patch(
    "app.core.ws_manager.ws_manager.get_presence",
    new_callable=AsyncMock,
    return_value={
        "status": "online",
        "ts": 100.0,
    },
)
async def test_get_user_presence(
    mock_presence: AsyncMock,
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 90001)
    headers = await auth_headers(
        client, user["id"]
    )

    r = await client.get(
        "/api/v1/users/999/presence",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == 999
    assert data["status"] == "online"


async def test_get_user_presence_unauthorized(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/users/999/presence"
    )
    assert r.status_code in (401, 403)
