from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from app.core.auth import create_access_token
from app.dependencies import get_current_user, get_db
from app.main import create_app
from app.models.user import User
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


async def test_require_admin_non_admin_raises_403(
    db_engine,
) -> None:
    factory: async_sessionmaker[AsyncSession] = (
        async_sessionmaker(
            db_engine, expire_on_commit=False
        )
    )

    fake_user = User(
        id=9999,
        telegram_id=9999,
        first_name="Regular",
        is_active=True,
        is_admin=False,
    )

    async def _override_get_db():
        async with factory() as session:
            yield session

    async def _override_get_current_user():
        return fake_user

    application = create_app()
    application.dependency_overrides[get_db] = (
        _override_get_db
    )
    application.dependency_overrides[
        get_current_user
    ] = _override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as ac:
        token = create_access_token(9999, False)
        headers = {
            "Authorization": f"Bearer {token}"
        }

        resp = await ac.get(
            "/api/v1/admin/tracks", headers=headers
        )

    assert resp.status_code == 403
