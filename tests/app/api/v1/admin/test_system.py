"""Tests for admin system endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    admin_bearer_for_user,
    create_test_user,
    grant_admin_capability,
)

pytestmark = pytest.mark.anyio


async def test_outbound_status_degrades_on_snapshot_error(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dotsound_private_core.services.outbound as outbound

    async def _broken_status() -> dict:
        raise RuntimeError("boom")

    admin = await create_test_user(client, 151_501)
    await grant_admin_capability(
        db_session,
        admin["id"],
        "metrics.view",
    )
    headers = await admin_bearer_for_user(
        client,
        db_session,
        user_id=admin["id"],
    )
    monkeypatch.setattr(outbound, "outbound_status", _broken_status)

    response = await client.get(
        "/api/v1/admin/system/outbound-status",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "error": "RuntimeError",
    }
