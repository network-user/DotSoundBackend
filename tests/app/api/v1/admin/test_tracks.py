import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    admin_bearer_for_user,
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_admin_list_tracks(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130001)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )

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
    admin_h = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
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
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )

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
    assert r.status_code == 401
