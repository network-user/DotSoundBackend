import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from tests.conftest import (
    admin_bearer_for_user,
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def _mark_track_playable(
    db_session: AsyncSession, track_id: int
) -> None:
    """Force the freshly-uploaded test track into a playable state.

    `create_test_track` leaves `file_key=None` because the S3 upload
    is mocked, but `ensure_track_addable_to_user_playlist` rejects
    such rows. Setting `file_key` here mirrors the post-transcoding
    state without invoking the real worker.
    """
    await db_session.execute(
        update(Track)
        .where(Track.id == track_id)
        .values(
            file_key=f"tracks/{track_id}.mp3",
            processing_status="active",
        )
    )
    await db_session.commit()


async def test_admin_playlist_reorder(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130_600)
    admin_h = await admin_bearer_for_user(
        client,
        db_session,
        user_id=admin["id"],
    )
    user_h = await auth_headers(client, admin["id"])

    pr = await client.post(
        "/api/v1/playlists",
        json={"name": "Admin PL", "is_public": True},
        headers=user_h,
    )
    assert pr.status_code == 201
    playlist_id = pr.json()["id"]

    t1 = await create_test_track(
        client,
        "PL A",
        uploader_id=admin["id"],
    )
    t2 = await create_test_track(
        client,
        "PL B",
        uploader_id=admin["id"],
    )
    await _mark_track_playable(db_session, t1["id"])
    await _mark_track_playable(db_session, t2["id"])

    r1 = await client.post(
        f"/api/v1/admin/playlists/{playlist_id}/tracks/{t1['id']}",
        headers=admin_h,
    )
    assert r1.status_code == 204
    r2 = await client.post(
        f"/api/v1/admin/playlists/{playlist_id}/tracks/{t2['id']}",
        headers=admin_h,
    )
    assert r2.status_code == 204

    gr = await client.get(
        f"/api/v1/admin/playlists/{playlist_id}",
        headers=admin_h,
    )
    assert gr.status_code == 200
    assert [x["id"] for x in gr.json()["tracks"]] == [t1["id"], t2["id"]]

    rr = await client.put(
        f"/api/v1/admin/playlists/{playlist_id}/track-order",
        headers=admin_h,
        json={"track_ids": [t2["id"], t1["id"]]},
    )
    assert rr.status_code == 204

    gr2 = await client.get(
        f"/api/v1/admin/playlists/{playlist_id}",
        headers=admin_h,
    )
    assert [x["id"] for x in gr2.json()["tracks"]] == [
        t2["id"],
        t1["id"],
    ]


async def test_admin_playlist_list(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130_601)
    admin_h = await admin_bearer_for_user(
        client,
        db_session,
        user_id=admin["id"],
    )
    user_h = await auth_headers(client, admin["id"])

    await client.post(
        "/api/v1/playlists",
        json={"name": "ListMe", "is_public": True},
        headers=user_h,
    )

    lr = await client.get(
        "/api/v1/admin/playlists?search=ListMe",
        headers=admin_h,
    )
    assert lr.status_code == 200
    assert lr.json()["total"] >= 1
