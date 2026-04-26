import pytest
from dirty_equals import IsInstance, IsPartialDict
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    admin_bearer_for_user,
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_admin_list_complaints(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 120001)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )

    r = await client.get(
        "/api/v1/admin/complaints",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json() == IsPartialDict(
        items=IsInstance(list),
        total=IsInstance(int),
    )


async def test_admin_resolve_complaint(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 120002)
    admin_h = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )

    reporter = await create_test_user(client, 120003)
    reporter_h = await auth_headers(
        client, reporter["id"]
    )
    track = await create_test_track(
        client, "Complaint Track",
        uploader_id=reporter["id"],
    )

    await client.post(
        "/api/v1/complaints",
        json={
            "track_id": track["id"],
            "reason": "This is a test complaint reason",
        },
        headers=reporter_h,
    )

    list_r = await client.get(
        "/api/v1/admin/complaints",
        headers=admin_h,
    )
    items = list_r.json()["items"]
    assert len(items) >= 1

    complaint_id = items[0]["id"]
    r = await client.patch(
        f"/api/v1/admin/complaints"
        f"/{complaint_id}/resolve",
        headers=admin_h,
    )
    assert r.status_code == 200
    assert r.json()["is_resolved"] is True


async def test_non_admin_rejected(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 120004)
    headers = await auth_headers(client, user["id"])
    r = await client.get(
        "/api/v1/admin/complaints",
        headers=headers,
    )
    assert r.status_code == 401
