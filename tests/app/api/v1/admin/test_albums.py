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


async def test_admin_album_list_and_reorder(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130_500)
    admin_h = await admin_bearer_for_user(
        client,
        db_session,
        user_id=admin["id"],
    )
    user_h = await auth_headers(client, admin["id"])

    ar = await client.post(
        "/api/v1/albums",
        json={"title": "Admin reorder", "is_public": True},
        headers=user_h,
    )
    assert ar.status_code == 201
    album_id = ar.json()["id"]

    t1 = await create_test_track(
        client,
        "First",
        uploader_id=admin["id"],
    )
    t2 = await create_test_track(
        client,
        "Second",
        uploader_id=admin["id"],
    )

    r1 = await client.post(
        f"/api/v1/admin/albums/{album_id}/tracks/{t1['id']}",
        headers=admin_h,
    )
    assert r1.status_code == 204
    r2 = await client.post(
        f"/api/v1/admin/albums/{album_id}/tracks/{t2['id']}",
        headers=admin_h,
    )
    assert r2.status_code == 204

    gr = await client.get(
        f"/api/v1/admin/albums/{album_id}",
        headers=admin_h,
    )
    assert gr.status_code == 200
    body = gr.json()
    assert [x["id"] for x in body["tracks"]] == [t1["id"], t2["id"]]

    rr = await client.put(
        f"/api/v1/admin/albums/{album_id}/track-order",
        headers=admin_h,
        json={"track_ids": [t2["id"], t1["id"]]},
    )
    assert rr.status_code == 204

    gr2 = await client.get(
        f"/api/v1/admin/albums/{album_id}",
        headers=admin_h,
    )
    assert [x["id"] for x in gr2.json()["tracks"]] == [
        t2["id"],
        t1["id"],
    ]


async def test_admin_album_patch_and_list(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130_501)
    admin_h = await admin_bearer_for_user(
        client,
        db_session,
        user_id=admin["id"],
    )
    user_h = await auth_headers(client, admin["id"])

    ar = await client.post(
        "/api/v1/albums",
        json={"title": "Patch me", "is_public": True},
        headers=user_h,
    )
    album_id = ar.json()["id"]

    pr = await client.patch(
        f"/api/v1/admin/albums/{album_id}",
        headers=admin_h,
        json={"title": "Patched", "is_public": False},
    )
    assert pr.status_code == 200
    assert pr.json()["title"] == "Patched"
    assert pr.json()["is_public"] is False

    lr = await client.get(
        "/api/v1/admin/albums?search=Patched",
        headers=admin_h,
    )
    assert lr.status_code == 200
    items = lr.json()["items"]
    assert any(i["id"] == album_id for i in items)


async def test_non_admin_album_routes_rejected(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 130_502)
    headers = await auth_headers(client, user["id"])
    r = await client.get(
        "/api/v1/admin/albums",
        headers=headers,
    )
    assert r.status_code == 401
