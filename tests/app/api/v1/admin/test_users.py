import pytest
from dirty_equals import IsInstance, IsInt, IsPartialDict
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.conftest import (
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


async def test_admin_list_users(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140001)
    await _make_admin(db_session, admin["id"])
    headers = await auth_headers(client, admin["id"])

    r = await client.get(
        "/api/v1/admin/users",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json() == IsPartialDict(
        items=IsInstance(list),
        total=IsInt(ge=1),
    )


async def test_admin_update_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140002)
    await _make_admin(db_session, admin["id"])
    admin_h = await auth_headers(client, admin["id"])

    target = await create_test_user(client, 140003)

    r = await client.patch(
        f"/api/v1/admin/users/{target['id']}",
        json={"display_name": "Updated Name"},
        headers=admin_h,
    )
    assert r.status_code == 200
    assert r.json()["display_name"] == "Updated Name"


async def test_admin_update_user_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140004)
    await _make_admin(db_session, admin["id"])
    headers = await auth_headers(client, admin["id"])

    r = await client.patch(
        "/api/v1/admin/users/99999",
        json={"is_active": False},
        headers=headers,
    )
    assert r.status_code == 404


async def test_non_admin_rejected(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 140005)
    headers = await auth_headers(client, user["id"])
    r = await client.get(
        "/api/v1/admin/users",
        headers=headers,
    )
    assert r.status_code == 403
