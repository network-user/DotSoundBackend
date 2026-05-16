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


async def _admin_headers(
    client: AsyncClient,
    db_session: AsyncSession,
    telegram_id: int,
) -> dict[str, str]:
    admin = await create_test_user(client, telegram_id)
    await grant_admin_capability(
        db_session,
        admin["id"],
        "metrics.view",
    )
    return await admin_bearer_for_user(
        client,
        db_session,
        user_id=admin["id"],
    )


async def test_outbound_status_degrades_on_snapshot_error(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dotsound_private_core.services.outbound as outbound

    async def _broken_status() -> dict:
        raise RuntimeError("boom")

    headers = await _admin_headers(client, db_session, 151_501)
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


async def test_outbound_status_uses_backend_static_proxy_mode(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dotsound_private_core.services.outbound as outbound

    import app.api.v1.admin.system as system_mod

    class _Settings:
        outbound_static_proxy_urls_list = [
            "http://proxy-a.test:8080",
            "http://proxy-b.test:8080",
        ]
        tor_pool_enabled = False
        tor_control_port = 9151
        tor_pool_size = 10
        tor_circuit_max_age_seconds = 600

    async def _private_status() -> dict:
        return {
            "mode": "tor",
            "tor": {
                "available": True,
                "circuit_uses_cap": 50,
                "newnym_min_interval_s": 10.0,
                "control_port": 9051,
            },
            "proxies": {
                "configured": 0,
                "prefer_tor": True,
                "service_specific": {},
            },
            "quarantine": {},
            "limits": {},
            "backend": "httpx",
            "services": [],
            "rotation_events": {},
            "recent_requests": [],
        }

    headers = await _admin_headers(client, db_session, 151_502)
    monkeypatch.setattr(system_mod, "settings", _Settings())
    monkeypatch.setattr(outbound, "outbound_status", _private_status)
    monkeypatch.setattr(
        "app.services.tor_pool.get_tor_pool",
        lambda: None,
    )

    response = await client.get(
        "/api/v1/admin/system/outbound-status",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["mode"] == "proxy"
    assert body["tor"]["available"] is False
    assert body["tor"]["control_port"] is None
    assert body["proxies"]["configured"] == 2
    assert body["proxies"]["prefer_tor"] is False
