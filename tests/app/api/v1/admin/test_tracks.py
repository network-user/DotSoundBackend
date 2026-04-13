import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.conftest import (
    auth_headers,
    create_test_track,
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


async def test_admin_list_tracks(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130001)
    await _make_admin(db_session, admin["id"])
    headers = await auth_headers(client, admin["id"])

    r = await client.get(
        "/api/v1/admin/tracks",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1


async def test_admin_toggle_track_visibility(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130002)
    await _make_admin(db_session, admin["id"])
    admin_h = await auth_headers(client, admin["id"])
    track = await create_test_track(
        client, "Visible Track",
        uploader_id=admin["id"],
    )

    r = await client.patch(
        f"/api/v1/admin/tracks"
        f"/{track['id']}/visibility",
        params={"is_active": False},
        headers=admin_h,
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


async def test_admin_delete_track_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130003)
    await _make_admin(db_session, admin["id"])
    headers = await auth_headers(client, admin["id"])

    r = await client.delete(
        "/api/v1/admin/tracks/99999",
        headers=headers,
    )
    assert r.status_code == 404


async def test_non_admin_rejected(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 130004)
    headers = await auth_headers(client, user["id"])
    r = await client.get(
        "/api/v1/admin/tracks",
        headers=headers,
    )
    assert r.status_code == 403
