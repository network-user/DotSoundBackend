import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.models.background_job import BackgroundJob
from app.models.lyrics import TrackLyrics
from app.models.track import Track
from app.models.track_playback_failure_event import (
    TrackPlaybackFailureEvent,
)
from app.services.telegram_import_backfill_service import (
    TelegramImportBackfillItem,
    TelegramImportBackfillReport,
)
from tests.conftest import (
    admin_bearer_for_user,
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


class _PlaybackRepairKicker:
    def with_labels(self, **_labels: str) -> "_PlaybackRepairKicker":
        return self

    async def kiq(self, **_payload: object) -> None:
        return None


async def _create_track(
    db_session: AsyncSession,
    *,
    title: str,
    uploader_id: int,
) -> dict[str, int | str]:
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
    await db_session.commit()
    assert track.id is not None
    return {"id": track.id, "title": track.title}


async def _create_soundcloud_track(
    db_session: AsyncSession,
    *,
    title: str,
    uploader_id: int,
    checked_at: datetime | None = None,
) -> Track:
    slug = title.lower().replace(" ", "-")
    track = Track(
        title=title,
        artist="Artist",
        uploaded_by_id=uploader_id,
        is_active=True,
        is_public=True,
        source="soundcloud",
        catalog_type="external_reference",
        access_mode="third_party_stream",
        source_platform="soundcloud",
        processing_status="active",
        sc_url=f"https://soundcloud.com/test/{slug}",
        source_url=f"https://soundcloud.com/test/{slug}",
        canonical_source_url=f"https://soundcloud.com/test/{slug}",
        playback_last_checked_at=checked_at,
    )
    db_session.add(track)
    await db_session.commit()
    await db_session.refresh(track)
    return track


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
    matched = await _create_track(
        db_session,
        title="Needle Bulk Track",
        uploader_id=admin["id"],
    )
    await _create_track(
        db_session,
        title="Other Bulk Track",
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


async def test_admin_list_tracks_exposes_and_filters_lyrics_sync_status(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130015)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    synced = await _create_track(
        db_session,
        title="Synced Timecodes",
        uploader_id=admin["id"],
    )
    unsynced = await _create_track(
        db_session,
        title="Plain Lyrics",
        uploader_id=admin["id"],
    )
    await _create_track(
        db_session,
        title="No Lyrics",
        uploader_id=admin["id"],
    )
    db_session.add_all(
        [
            TrackLyrics(
                track_id=int(synced["id"]),
                plain_text="line",
                synced_lines=[{"start": 0.0, "end": 1.0, "line": "line"}],
            ),
            TrackLyrics(
                track_id=int(unsynced["id"]),
                plain_text="plain",
                synced_lines=[],
            ),
        ]
    )
    await db_session.commit()

    r = await client.get(
        "/api/v1/admin/tracks",
        headers=headers,
        params={"lyrics_sync_status": "synced"},
    )
    assert r.status_code == 200
    data = r.json()
    ids = [item["id"] for item in data["items"]]
    assert ids == [synced["id"]]
    assert data["items"][0]["has_synced_timecodes"] is True
    assert data["items"][0]["lyrics_sync_status"] == "synced"

    r = await client.get(
        "/api/v1/admin/tracks/ids",
        headers=headers,
        params={"lyrics_sync_status": "unsynced"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["ids"] == [unsynced["id"]]


async def test_admin_playback_unavailable_includes_diagnostics(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130006)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    track = await _create_track(
        db_session,
        title="Broken SoundCloud",
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
            playback_last_checked_at=now,
            playback_last_repair_attempt_at=now,
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
    assert row["playback_last_checked_at"] is not None
    assert row["playback_last_repair_attempt_at"] is not None


async def test_admin_playback_unavailable_filters_latest_diagnostic(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130007)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    now = datetime.now(UTC)
    matched = Track(
        title="Matched Broken SoundCloud",
        artist="Artist",
        uploaded_by_id=admin["id"],
        is_active=True,
        is_public=True,
        source="external",
        catalog_type="external-source",
        access_mode="third_party_stream",
        source_platform="soundcloud",
        playback_last_failure_at=now,
        playback_last_http_status=502,
        playback_last_failure_source="server_recovery_exhausted",
    )
    other = Track(
        title="Other Broken SoundCloud",
        artist="Artist",
        uploaded_by_id=admin["id"],
        is_active=True,
        is_public=True,
        source="external",
        catalog_type="external-source",
        access_mode="third_party_stream",
        source_platform="soundcloud",
        playback_last_failure_at=now,
        playback_last_http_status=502,
        playback_last_failure_source="server_recovery_exhausted",
    )
    stale = Track(
        title="Stale Broken SoundCloud",
        artist="Artist",
        uploaded_by_id=admin["id"],
        is_active=True,
        is_public=True,
        source="external",
        catalog_type="external-source",
        access_mode="third_party_stream",
        source_platform="soundcloud",
        playback_last_failure_at=now,
        playback_last_http_status=502,
        playback_last_failure_source="server_recovery_exhausted",
    )
    db_session.add_all([matched, other, stale])
    await db_session.flush()
    assert matched.id is not None
    assert other.id is not None
    assert stale.id is not None
    db_session.add_all(
        [
            TrackPlaybackFailureEvent(
                track_id=matched.id,
                user_id=admin["id"],
                source="server_recovery_exhausted",
                http_status=502,
                detail_truncated=json.dumps(
                    {
                        "code": "soundcloud_stream_unavailable",
                        "reason": (
                            "provider_manifest_not_found_for_all_formats"
                        ),
                    }
                ),
                created_at=now,
            ),
            TrackPlaybackFailureEvent(
                track_id=other.id,
                user_id=admin["id"],
                source="server_recovery_exhausted",
                http_status=502,
                detail_truncated=json.dumps(
                    {
                        "code": "audio_proxy_timeout",
                        "reason": "manifest_fetch_timeout",
                    }
                ),
                created_at=now,
            ),
            TrackPlaybackFailureEvent(
                track_id=stale.id,
                user_id=admin["id"],
                source="server_recovery_exhausted",
                http_status=502,
                detail_truncated=json.dumps(
                    {
                        "code": "soundcloud_stream_unavailable",
                        "reason": "old_failure",
                    }
                ),
                created_at=now - timedelta(minutes=2),
            ),
            TrackPlaybackFailureEvent(
                track_id=stale.id,
                user_id=admin["id"],
                source="server_recovery_exhausted",
                http_status=502,
                detail_truncated=json.dumps(
                    {
                        "code": "audio_proxy_timeout",
                        "reason": "latest_failure",
                    }
                ),
                created_at=now + timedelta(minutes=1),
            ),
        ]
    )
    await db_session.commit()

    r = await client.get(
        "/api/v1/admin/tracks/playback-health/unavailable",
        headers=headers,
        params={"playback_error": "soundcloud_stream_unavailable"},
    )

    assert r.status_code == 200
    ids = [item["id"] for item in r.json()["items"]]
    assert matched.id in ids
    assert other.id not in ids
    assert stale.id not in ids

    ids_response = await client.get(
        "/api/v1/admin/tracks/ids",
        headers=headers,
        params={
            "scope": "playback_failures",
            "playback_error": "provider_manifest_not_found",
        },
    )

    assert ids_response.status_code == 200
    filtered_ids = ids_response.json()["ids"]
    assert matched.id in filtered_ids
    assert other.id not in filtered_ids
    assert stale.id not in filtered_ids


async def test_admin_soundcloud_encrypted_unsupported_filter(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130011)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    old_embed = Track(
        title="Old SC Embed",
        artist="Artist",
        uploaded_by_id=admin["id"],
        is_active=True,
        is_public=True,
        source="soundcloud",
        catalog_type="external_reference",
        access_mode="official_embed",
        source_platform="soundcloud",
        processing_status="active",
        sc_url="https://soundcloud.com/test/old-embed",
    )
    archived = Track(
        title="Archived SC Encrypted",
        artist="Artist",
        uploaded_by_id=admin["id"],
        is_active=False,
        is_public=False,
        source="soundcloud",
        catalog_type="external_reference",
        access_mode="third_party_stream",
        source_platform="soundcloud",
        processing_status="active",
        sc_url="https://soundcloud.com/test/archived-encrypted",
        deleted_reason="encrypted_hls_unsupported",
        playback_last_failure_at=datetime.now(UTC),
    )
    other_embed = Track(
        title="Other Official Embed",
        artist="Artist",
        uploaded_by_id=admin["id"],
        is_active=True,
        is_public=True,
        source="external",
        catalog_type="external_reference",
        access_mode="official_embed",
        source_platform="youtube",
        processing_status="active",
    )
    db_session.add_all([old_embed, archived, other_embed])
    await db_session.commit()
    assert old_embed.id is not None
    assert archived.id is not None
    assert other_embed.id is not None

    r = await client.get(
        "/api/v1/admin/tracks/playback-health/"
        "soundcloud-encrypted-unsupported",
        headers=headers,
    )

    assert r.status_code == 200
    ids = [item["id"] for item in r.json()["items"]]
    assert old_embed.id in ids
    assert archived.id in ids
    assert other_embed.id not in ids
    archived_row = next(
        item for item in r.json()["items"] if item["id"] == archived.id
    )
    assert archived_row["deleted_reason"] == "encrypted_hls_unsupported"

    ids_response = await client.get(
        "/api/v1/admin/tracks/ids",
        headers=headers,
        params={"scope": "sc_encrypted_unsupported"},
    )

    assert ids_response.status_code == 200
    filtered_ids = ids_response.json()["ids"]
    assert old_embed.id in filtered_ids
    assert archived.id in filtered_ids
    assert other_embed.id not in filtered_ids


async def test_admin_cleanup_soundcloud_encrypted_unsupported_embeds(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130012)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    old_embed = Track(
        title="Cleanup SC Embed",
        artist="Artist",
        uploaded_by_id=admin["id"],
        is_active=True,
        is_public=True,
        source="soundcloud",
        catalog_type="external_reference",
        access_mode="official_embed",
        source_platform="soundcloud",
        processing_status="active",
        sc_url="https://soundcloud.com/test/cleanup-sc-embed",
        source_url="https://soundcloud.com/test/cleanup-sc-embed",
    )
    other_embed = Track(
        title="Cleanup Other Embed",
        artist="Artist",
        uploaded_by_id=admin["id"],
        is_active=True,
        is_public=True,
        source="external",
        catalog_type="external_reference",
        access_mode="official_embed",
        source_platform="youtube",
        processing_status="active",
    )
    db_session.add_all([old_embed, other_embed])
    await db_session.commit()
    assert old_embed.id is not None
    assert other_embed.id is not None

    r = await client.post(
        "/api/v1/admin/tracks/playback-health/"
        "cleanup-soundcloud-encrypted-unsupported",
        headers=headers,
        json={"limit": 10},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["matched"] == 1
    assert body["updated"] == 1
    assert body["track_ids"] == [old_embed.id]
    await db_session.refresh(old_embed)
    await db_session.refresh(other_embed)
    assert old_embed.access_mode == "third_party_stream"
    assert old_embed.is_active is False
    assert old_embed.is_public is False
    assert old_embed.deleted_reason == "encrypted_hls_unsupported"
    assert old_embed.playback_last_failure_source == (
        "admin_sc_encrypted_cleanup"
    )
    assert old_embed.source_url == (
        "https://soundcloud.com/test/cleanup-sc-embed"
    )
    assert other_embed.access_mode == "official_embed"
    assert other_embed.is_active is True

    event = (
        await db_session.scalars(
            select(TrackPlaybackFailureEvent).where(
                TrackPlaybackFailureEvent.track_id == old_embed.id,
            )
        )
    ).one()
    detail = json.loads(event.detail_truncated or "{}")
    assert event.source == "admin_sc_encrypted_cleanup"
    assert event.http_status == 422
    assert detail["code"] == "soundcloud_encrypted_hls_unsupported"
    assert detail["reason"] == "encrypted_hls_unsupported"


async def test_admin_normalize_telegram_playback_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130013)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    report = TelegramImportBackfillReport(
        dry_run=False,
        found=2,
        enqueued=1,
        failed=1,
        items=[
            TelegramImportBackfillItem(
                track_id=11,
                status="enqueued",
                title="Telegram OK",
                file_key="telegram/ok.ogg",
                tmp_key="tmp-transcode/ok.ogg",
            ),
            TelegramImportBackfillItem(
                track_id=12,
                status="failed",
                title="Telegram Failed",
                file_key="telegram/fail.ogg",
                error="download failed",
            ),
        ],
    )

    with patch(
        "app.api.v1.admin.tracks.TelegramImportBackfillService"
    ) as service_cls:
        service = service_cls.return_value
        service.run = AsyncMock(return_value=report)
        r = await client.post(
            "/api/v1/admin/tracks/playback-health/normalize-telegram",
            headers=headers,
            json={"limit": 123, "dry_run": False},
        )

    assert r.status_code == 200
    service.run.assert_awaited_once_with(
        limit=123,
        dry_run=False,
        urgent=True,
    )
    body = r.json()
    assert body["dry_run"] is False
    assert body["found"] == 2
    assert body["enqueued"] == 1
    assert body["failed"] == 1
    assert body["detail"] == "telegram playback normalization queued"
    assert body["items"][0] == {
        "track_id": 11,
        "status": "enqueued",
        "title": "Telegram OK",
        "file_key": "telegram/ok.ogg",
        "tmp_key": "tmp-transcode/ok.ogg",
        "error": None,
    }


async def test_admin_playback_repair_returns_progress_id(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130008)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    track = await _create_track(
        db_session,
        title="Repair Progress Track",
        uploader_id=admin["id"],
    )

    with (
        patch(
            "app.services.playback_repair_progress.new_progress_id",
            return_value="progress-1",
        ),
        patch(
            "app.services.playback_repair_progress.safe_set_progress",
            new=AsyncMock(),
        ) as set_progress,
        patch(
            "app.services.background_jobs.enqueue",
            new=AsyncMock(return_value="job-1"),
        ) as enqueue,
    ):
        r = await client.post(
            f"/api/v1/admin/tracks/{track['id']}"
            "/playback-health/repair",
            headers=headers,
        )

    assert r.status_code == 200
    body = r.json()
    assert body["queued"] is True
    assert body["job_id"] == "job-1"
    assert body["progress_id"] == "progress-1"
    enqueue.assert_awaited_once()
    payload = enqueue.await_args.kwargs["payload"]
    assert payload == {
        "track_id": track["id"],
        "progress_id": "progress-1",
        "bypass_refresh_cache": True,
    }
    assert (
        enqueue.await_args.kwargs["job_id_payload_key"]
        == "background_job_id"
    )
    set_progress.assert_awaited_once_with(
        "progress-1",
        stage="queued",
        track_id=track["id"],
        log_line="queued by admin",
    )


async def test_admin_playback_repair_can_be_requeued_after_guard_window(
    client: AsyncClient,
    db_session: AsyncSession,
    db_engine: AsyncEngine,
) -> None:
    admin = await create_test_user(client, 130009)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    track = await _create_track(
        db_session,
        title="Repair Requeue Track",
        uploader_id=admin["id"],
    )
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        db_engine,
        expire_on_commit=False,
    )

    async def _slot_open(_key: str, *, ttl_seconds: int) -> bool:
        return True

    with (
        patch(
            "app.services.background_jobs.AsyncSessionLocal",
            factory,
        ),
        patch(
            "app.services.background_jobs.acquire_idempotency_slot",
            new=_slot_open,
        ),
        patch(
            "app.services.playback_repair_progress.new_progress_id",
            side_effect=["progress-1", "progress-2"],
        ),
        patch(
            "app.services.playback_repair_progress.safe_set_progress",
            new=AsyncMock(),
        ),
        patch(
            "app.services.playback_repair_worker"
            ".repair_track_playback_task.kicker",
            return_value=_PlaybackRepairKicker(),
        ),
    ):
        first = await client.post(
            f"/api/v1/admin/tracks/{track['id']}"
            "/playback-health/repair",
            headers=headers,
        )
        second = await client.post(
            f"/api/v1/admin/tracks/{track['id']}"
            "/playback-health/repair",
            headers=headers,
        )

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["queued"] is True
    assert second_body["queued"] is True
    assert first_body["job_id"] != second_body["job_id"]
    assert first_body["progress_id"] == "progress-1"
    assert second_body["progress_id"] == "progress-2"

    rows = [
        row
        for row in (
            await db_session.scalars(
                select(BackgroundJob).where(
                    BackgroundJob.idempotency_key
                    == f"playback-repair:track:{track['id']}"
                )
            )
        ).all()
    ]
    assert len(rows) == 2


async def test_admin_audit_soundcloud_playback_queues_unchecked_tracks(
    client: AsyncClient,
    db_session: AsyncSession,
    db_engine: AsyncEngine,
) -> None:
    admin = await create_test_user(client, 130010)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    unchecked = await _create_soundcloud_track(
        db_session,
        title="Audit One",
        uploader_id=admin["id"],
    )
    await _create_soundcloud_track(
        db_session,
        title="Audit Checked",
        uploader_id=admin["id"],
        checked_at=datetime.now(UTC),
    )
    await _create_track(
        db_session,
        title="Audit Internal",
        uploader_id=admin["id"],
    )
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        db_engine,
        expire_on_commit=False,
    )

    async def _slot_open(_key: str, *, ttl_seconds: int) -> bool:
        return True

    with (
        patch(
            "app.services.background_jobs.AsyncSessionLocal",
            factory,
        ),
        patch(
            "app.services.background_jobs.acquire_idempotency_slot",
            new=_slot_open,
        ),
        patch(
            "app.services.playback_repair_progress.new_progress_id",
            return_value="progress-sc-audit",
        ),
        patch(
            "app.services.playback_repair_progress.safe_set_progress",
            new=AsyncMock(),
        ),
        patch(
            "app.services.playback_repair_worker"
            ".repair_track_playback_task.kicker",
            return_value=_PlaybackRepairKicker(),
        ),
    ):
        r = await client.post(
            "/api/v1/admin/tracks/playback-health/audit-soundcloud",
            headers=headers,
            json={"limit": 10},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["requested"] == 1
    assert body["queued"] == 1
    assert body["skipped"] == 0

    rows = (
        await db_session.scalars(
            select(BackgroundJob).where(
                BackgroundJob.idempotency_key
                == f"playback-repair:track:{unchecked.id}"
            )
        )
    ).all()
    assert len(rows) == 1


async def test_admin_toggle_track_visibility(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130002)
    admin_h = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    track = await _create_track(
        db_session,
        title="Visible Track",
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
