from __future__ import annotations

import base64

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.conftest import (
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


_FERNET_KEY = base64.urlsafe_b64encode(
    b"0" * 32
).decode()


async def _make_admin(
    db_session: AsyncSession, user_id: int
) -> None:
    await db_session.execute(
        update(User)
        .where(User.id == user_id)
        .values(is_admin=True)
    )
    await db_session.commit()


async def test_metadata_for_non_admin_404(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 700001)
    headers = await auth_headers(
        client, user["id"]
    )
    r = await client.get(
        "/api/v1/admin/auth/metadata",
        headers=headers,
    )
    assert r.status_code == 404


async def test_metadata_for_admin_returns_flags(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 700002)
    await _make_admin(db_session, user["id"])
    headers = await auth_headers(
        client, user["id"]
    )
    r = await client.get(
        "/api/v1/admin/auth/metadata",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_admin"] is True
    assert body["admin_init"] is False
    assert body["admin_totp_enabled"] is False


async def test_init_start_for_non_admin_404(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 700003)
    headers = await auth_headers(
        client, user["id"]
    )
    r = await client.post(
        "/api/v1/admin/auth/init/start",
        headers=headers,
    )
    assert r.status_code == 404


async def test_init_start_for_admin_returns_secret(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 700004)
    await _make_admin(db_session, user["id"])
    headers = await auth_headers(
        client, user["id"]
    )
    r = await client.post(
        "/api/v1/admin/auth/init/start",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "secret_b32" in body
    assert "otpauth_uri" in body


async def test_login_locked_user_returns_423(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await create_test_user(client, 700005)
    await _make_admin(db_session, user["id"])
    headers = await auth_headers(
        client, user["id"]
    )

    async def _yes(_user_id: int) -> bool:
        return True

    monkeypatch.setattr(
        "app.api.v1.admin.auth.is_locked_out",
        _yes,
    )
    r = await client.post(
        "/api/v1/admin/auth/login",
        json={
            "code": "000000",
            "fingerprint": "fp_login_test_long_enough",
        },
        headers=headers,
    )
    assert r.status_code == 423
