from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lyrics import TrackLyrics
from app.models.lyrics_job import LyricsJob
from app.models.track import Track
from tests.conftest import admin_bearer_for_user, create_test_user

pytestmark = pytest.mark.anyio


async def _unsynced_track(
    db_session: AsyncSession,
    *,
    title: str,
    uploader_id: int,
) -> int:
    track = Track(
        title=title,
        artist="Artist",
        uploaded_by_id=uploader_id,
        is_active=True,
        is_public=True,
        source="internal",
        catalog_type="ugc",
        access_mode="internal_stream",
        processing_status="active",
        file_key=f"tests/{title}.mp3",
    )
    db_session.add(track)
    await db_session.flush()
    db_session.add(
        TrackLyrics(
            track_id=int(track.id),
            plain_text="line one\nline two",
            synced_lines=None,
        )
    )
    await db_session.commit()
    assert track.id is not None
    return int(track.id)


@patch(
    "app.services.lyrics_cascade.start_cascade",
    new_callable=AsyncMock,
    return_value="remote_whisper",
)
@patch(
    "app.services.compute_router.get_routing_mode",
    new_callable=AsyncMock,
    return_value="auto",
)
@patch(
    "app.services.lyrics_worker.set_cached_lyrics_result",
    new_callable=AsyncMock,
)
@patch(
    "app.services.lyrics_worker.set_lyrics_progress",
    new_callable=AsyncMock,
)
async def test_timecode_sync_enqueue_and_queue(
    _progress: AsyncMock,
    _cache: AsyncMock,
    _routing: AsyncMock,
    _cascade: AsyncMock,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 131001)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    track_id = await _unsynced_track(
        db_session,
        title="Timecode Sync Me",
        uploader_id=admin["id"],
    )

    enq = await client.post(
        "/api/v1/admin/tracks/lyrics-timecode-sync/enqueue",
        headers=headers,
        json={"track_ids": [track_id], "limit": 10},
    )
    assert enq.status_code == 200
    body = enq.json()
    assert body["enqueued"] == 1
    assert len(body["job_ids"]) == 1

    job_id = body["job_ids"][0]
    row = (
        await db_session.execute(
            select(LyricsJob).where(LyricsJob.id == job_id)
        )
    ).scalar_one()
    assert row.request_align_existing_text is True
    assert row.requested_by_user_id == admin["id"]

    q = await client.get(
        "/api/v1/admin/tracks/lyrics-timecode-sync/queue",
        headers=headers,
    )
    assert q.status_code == 200
    snapshot = q.json()
    assert snapshot["counts"]["queued"] >= 1
    assert any(
        j["id"] == job_id for j in snapshot["queued"]
    )

    pri = await client.patch(
        f"/api/v1/admin/tracks/lyrics-timecode-sync/jobs/{job_id}/priority",
        headers=headers,
        json={"queue_priority": 42},
    )
    assert pri.status_code == 200
    assert pri.json()["queue_priority"] == 42

    bump = await client.patch(
        f"/api/v1/admin/tracks/lyrics-timecode-sync/jobs/{job_id}/priority",
        headers=headers,
        json={"bump_next": True},
    )
    assert bump.status_code == 200
    assert bump.json()["queue_priority"] >= 42


@patch(
    "app.services.lyrics_cascade.start_cascade",
    new_callable=AsyncMock,
    return_value="remote_whisper",
)
@patch(
    "app.services.compute_router.get_routing_mode",
    new_callable=AsyncMock,
    return_value="auto",
)
@patch(
    "app.services.lyrics_worker.set_cached_lyrics_result",
    new_callable=AsyncMock,
)
@patch(
    "app.services.lyrics_worker.set_lyrics_progress",
    new_callable=AsyncMock,
)
async def test_timecode_sync_queue_mine_filter(
    _progress: AsyncMock,
    _cache: AsyncMock,
    _routing: AsyncMock,
    _cascade: AsyncMock,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin_a = await create_test_user(client, 131002)
    admin_b = await create_test_user(client, 131003)
    headers_a = await admin_bearer_for_user(
        client, db_session, user_id=admin_a["id"]
    )
    headers_b = await admin_bearer_for_user(
        client, db_session, user_id=admin_b["id"]
    )
    track_id = await _unsynced_track(
        db_session,
        title="Mine Filter Track",
        uploader_id=admin_a["id"],
    )

    await client.post(
        "/api/v1/admin/tracks/lyrics-timecode-sync/enqueue",
        headers=headers_a,
        json={"track_ids": [track_id], "limit": 5},
    )

    all_q = await client.get(
        "/api/v1/admin/tracks/lyrics-timecode-sync/queue",
        headers=headers_b,
    )
    mine_q = await client.get(
        "/api/v1/admin/tracks/lyrics-timecode-sync/queue",
        headers=headers_b,
        params={"mine": True},
    )
    assert all_q.status_code == 200
    assert mine_q.status_code == 200
    assert len(all_q.json()["queued"]) >= 1
    assert mine_q.json()["queued"] == []


@patch(
    "app.services.lyrics_job_cancel.cancel_lyrics_job_for_admin",
    new_callable=AsyncMock,
    return_value={"status": "cancelled", "job_status": "cancelled"},
)
async def test_timecode_sync_cancel_align_job(
    _cancel: AsyncMock,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 131004)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    track_id = await _unsynced_track(
        db_session,
        title="Cancel Align",
        uploader_id=admin["id"],
    )
    job = LyricsJob(
        id="lj_timecode_cancel_test",
        track_id=track_id,
        progress_id="prog_cancel_test",
        requested_by_user_id=admin["id"],
        profile="catalog_only",
        status="queued",
        request_with_sync=True,
        request_align_existing_text=True,
    )
    db_session.add(job)
    await db_session.commit()

    res = await client.post(
        "/api/v1/admin/tracks/lyrics-timecode-sync/jobs/"
        f"{job.id}/cancel",
        headers=headers,
        json={},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"
    _cancel.assert_awaited_once()


async def test_timecode_sync_queue_since_hours_filter(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 131005)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    track_id = await _unsynced_track(
        db_session,
        title="Since Filter",
        uploader_id=admin["id"],
    )
    stale_created = datetime.now(UTC) - timedelta(days=3)
    old_job = LyricsJob(
        id="lj_timecode_old",
        track_id=track_id,
        progress_id="prog_old",
        requested_by_user_id=admin["id"],
        profile="catalog_only",
        status="done",
        request_with_sync=True,
        request_align_existing_text=True,
        created_at=stale_created,
        finished_at=stale_created,
    )
    db_session.add(old_job)
    await db_session.commit()

    recent = await client.get(
        "/api/v1/admin/tracks/lyrics-timecode-sync/queue",
        headers=headers,
        params={"since_hours": 24},
    )
    assert recent.status_code == 200
    ids = {j["id"] for j in recent.json()["recent"]}
    assert "lj_timecode_old" not in ids


async def test_timecode_queue_treats_scalar_synced_lines_as_unsynced(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 131098)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    track_id = await _unsynced_track(
        db_session,
        title="Scalar Synced Lines",
        uploader_id=admin["id"],
    )
    row = (
        await db_session.execute(
            select(TrackLyrics).where(TrackLyrics.track_id == track_id)
        )
    ).scalar_one()
    row.synced_lines = {"invalid": "object-not-array"}
    await db_session.commit()

    response = await client.get(
        "/api/v1/admin/tracks/lyrics-timecode-sync/queue",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["candidate_count"] >= 1


async def test_timecode_sync_queue_reports_missing_migration(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from sqlalchemy.exc import ProgrammingError

    admin = await create_test_user(client, 131099)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    orig = Exception(
        'column "request_align_existing_text" of relation '
        '"lyrics_jobs" does not exist'
    )
    with patch(
        "app.repositories.admin_lyrics_timecode_sync."
        "AdminLyricsTimecodeSyncRepository.list_align_jobs",
        new_callable=AsyncMock,
        side_effect=ProgrammingError(
            "SELECT",
            {},
            orig,
        ),
    ):
        response = await client.get(
            "/api/v1/admin/tracks/lyrics-timecode-sync/queue",
            headers=headers,
        )
    assert response.status_code == 503
    assert response.json()["detail"] == "migration_0119_required"
