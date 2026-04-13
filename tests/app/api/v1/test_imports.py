from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, create_test_user

pytestmark = pytest.mark.anyio


async def test_scan_telegram_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.post("/api/v1/import/telegram")
    assert r.status_code == 401


async def test_get_import_status_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/import/1/status")
    assert r.status_code == 401


async def test_get_active_import_none(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 90001)
    headers = await auth_headers(client, user["id"])
    with patch(
        "app.services.import_service"
        ".ImportService.get_active_job",
        new_callable=AsyncMock,
        return_value=None,
    ):
        r = await client.get(
            "/api/v1/import/active",
            headers=headers,
        )
    assert r.status_code == 200
    assert r.json() is None


async def test_cancel_import_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/import/1/cancel",
    )
    assert r.status_code == 401
