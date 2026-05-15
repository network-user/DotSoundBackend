import json
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.track_playback_failure_event import (
    TrackPlaybackFailureEvent,
)
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


async def test_admin_list_track_ids_search_filter(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130005)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    matched = await create_test_track(
        client,
        "Needle Bulk Track",
        uploader_id=admin["id"],
    )
    await create_test_track(
        client,
        "Other Bulk Track",
        uploader_id=admin["id"],
    )

    r = await client.get(
        "/api/v1/admin/tracks/ids",
        headers=headers,
        params={"search": "Needle Bulk"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["ids"] == [matched["id"]]


async def test_admin_playback_unavailable_includes_diagnostics(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130006)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    track = await create_test_track(
        client,
        "Broken SoundCloud",
        uploader_id=admin["id"],
    )
    detail = {
        "code": "soundcloud_stream_unavailable",
        "reason": "provider_manifest_not_found_for_all_formats",
        "stage": "transcoding_manifest",
        "upstream_status": 404,
        "attempted_protocols": ["progressive", "hls"],
    }
    now = datetime.now(UTC)
    await db_session.execute(
        update(Track)
        .where(Track.id == track["id"])
        .values(
            playback_last_failure_at=now,
            playback_last_http_status=502,
            playback_last_failure_source="server_recovery_exhausted",
        )
    )
    db_session.add(
        TrackPlaybackFailureEvent(
            track_id=track["id"],
            user_id=admin["id"],
            source="server_recovery_exhausted",
            http_status=502,
            detail_truncated=json.dumps(detail),
        )
    )
    await db_session.commit()

    r = await client.get(
        "/api/v1/admin/tracks/playback-health/unavailable",
        headers=headers,
    )

    assert r.status_code == 200
    row = next(
        item for item in r.json()["items"] if item["id"] == track["id"]
    )
    assert row["playback_last_error_code"] == (
        "soundcloud_stream_unavailable"
    )
    assert row["playback_last_error_reason"] == (
        "provider_manifest_not_found_for_all_formats"
    )
    assert row["playback_last_error_stage"] == "transcoding_manifest"
    assert row["playback_last_upstream_status"] == 404
    assert row["playback_last_attempted_protocols"] == [
        "progressive",
        "hls",
    ]


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
