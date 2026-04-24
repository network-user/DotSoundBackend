from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.conftest import (
    admin_bearer_for_user,
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def _make_admin(
    db_session: AsyncSession, user_id: int
) -> None:
    await db_session.execute(
        update(User)
        .where(User.id == user_id)
        .values(is_admin=True)
    )
    await db_session.commit()


async def test_admin_csrf_returns_token(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 600001)
    await _make_admin(db_session, user["id"])
    headers = await auth_headers(client, user["id"])
    r = await client.get(
        "/api/v1/admin/auth/csrf",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "csrf" in body
    assert len(body["csrf"]) > 16


async def test_admin_bearer_request_skips_csrf(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 600002)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    r = await client.patch(
        f"/api/v1/admin/users/{user['id']}",
        json={"display_name": "Renamed"},
        headers=headers,
    )
    assert r.status_code == 200


async def test_admin_get_no_csrf_required(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 600003)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    r = await client.get(
        "/api/v1/admin/users",
        headers=headers,
    )
    assert r.status_code == 200


async def test_admin_csrf_double_submit_match(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 600004)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )

    csrf_resp = await client.get(
        "/api/v1/admin/auth/csrf",
        headers=headers,
    )
    csrf_token = csrf_resp.json()["csrf"]

    r = await client.patch(
        f"/api/v1/admin/users/{user['id']}",
        json={"display_name": "OK"},
        headers={
            **headers,
            "X-Admin-CSRF": csrf_token,
        },
        cookies={"admin_csrf": csrf_token},
    )
    assert r.status_code == 200


async def test_admin_response_has_security_headers(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 600006)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    r = await client.get(
        "/api/v1/admin/users",
        headers=headers,
    )
    assert r.status_code == 200
    assert (
        "Content-Security-Policy" in r.headers
    )
    assert (
        r.headers["X-Frame-Options"] == "DENY"
    )
    assert (
        "no-referrer"
        in r.headers["Referrer-Policy"]
    )


async def test_admin_csrf_exempt_login_path(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 600007)
    await _make_admin(db_session, user["id"])
    headers = await auth_headers(client, user["id"])
    r = await client.post(
        "/api/v1/admin/auth/login",
        json={
            "code": "000000",
            "fingerprint": "fp_xxx_yyy_zz",
        },
        headers=headers,
    )
    assert r.status_code != 403 or (
        "CSRF" not in (r.text or "")
    )
