from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio_blob import AudioBlob
from app.models.track import Track
from app.models.user import User
from app.services.telegram_import_backfill_service import (
    TelegramImportBackfillService,
)

pytestmark = pytest.mark.anyio

_MOD = "app.services.ugc_playback_normalize_service"


async def _make_user(session: AsyncSession, telegram_id: int) -> User:
    user = User(
        telegram_id=telegram_id,
        username=f"u{telegram_id}",
        first_name="T",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _make_internal_upload_track(
    session: AsyncSession,
    *,
    user_id: int,
    file_key: str = "temp/uploads/1/uuid/track.mp3",
    hls_manifest_key: str | None = None,
) -> Track:
    track = Track(
        title="Manual Upload",
        artist="Artist",
        file_key=file_key,
        hls_manifest_key=hls_manifest_key,
        uploaded_by_id=user_id,
        is_active=True,
        is_public=True,
        source="internal",
        catalog_type="ugc",
        access_mode="internal_stream",
        processing_status="error",
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return track


async def _make_telegram_track(
    session: AsyncSession,
    *,
    user_id: int,
    file_key: str = "blobs/aa/raw.ogg",
    hls_manifest_key: str | None = None,
    blob_sha: str | None = "a" * 64,
) -> Track:
    blob_id: int | None = None
    if blob_sha is not None:
        blob = AudioBlob(
            content_sha256=blob_sha,
            s3_key=file_key,
            content_type="audio/ogg",
            size_bytes=10,
            ref_count=1,
        )
        session.add(blob)
        await session.flush()
        blob_id = blob.id
    track = Track(
        title="Telegram Song",
        artist="Artist",
        file_key=file_key,
        hls_manifest_key=hls_manifest_key,
        uploaded_by_id=user_id,
        is_active=True,
        is_public=True,
        source="telegram",
        source_platform="telegram",
        imported_from="telegram",
        catalog_type="ugc",
        access_mode="internal_stream",
        blob_id=blob_id,
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return track


async def test_dry_run_lists_manual_internal_upload_candidates(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, 6105)
    candidate = await _make_internal_upload_track(
        db_session,
        user_id=user.id,
        file_key="temp/raw/legacy_1_song.mp3",
    )

    service = TelegramImportBackfillService(db_session)
    report = await service.run(limit=10, dry_run=True)

    assert report.found == 1
    assert report.items[0].track_id == candidate.id


async def test_dry_run_lists_only_legacy_telegram_candidates(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, 6100)
    candidate = await _make_telegram_track(db_session, user_id=user.id)
    await _make_telegram_track(
        db_session,
        user_id=user.id,
        file_key="blobs/bb/ready.mp3",
        hls_manifest_key="hls-blobs/bb/ready/master.m3u8",
        blob_sha="b" * 64,
    )

    service = TelegramImportBackfillService(db_session)
    report = await service.run(limit=10, dry_run=True)

    assert report.dry_run is True
    assert report.found == 1
    assert report.enqueued == 0
    assert report.items[0].track_id == candidate.id
    assert report.items[0].status == "candidate"


@patch(f"{_MOD}.q.find_existing_job", new_callable=AsyncMock, return_value=None)
@patch(f"{_MOD}._source_object_exists", new_callable=AsyncMock, return_value=True)
@patch(f"{_MOD}._is_marked_unrecoverable", new_callable=AsyncMock, return_value=False)
@patch(f"{_MOD}._acquire_schedule_cooldown", new_callable=AsyncMock, return_value=True)
@patch(
    "app.services.search_index_notify.schedule_reindex_track",
    new_callable=AsyncMock,
)
@patch(
    f"{_MOD}.repair_ugc_playback_normalize_task.kiq",
    new_callable=AsyncMock,
)
@patch(f"{_MOD}.s3.upload_object", new_callable=AsyncMock)
@patch(
    f"{_MOD}.s3.download_object",
    new_callable=AsyncMock,
    return_value=b"raw-ogg",
)
async def test_apply_copies_raw_object_and_queues_repair(
    mock_download: AsyncMock,
    mock_upload: AsyncMock,
    mock_repair_kiq: AsyncMock,
    mock_reindex: AsyncMock,
    _mock_cooldown: AsyncMock,
    _mock_unrec: AsyncMock,
    _mock_exists: AsyncMock,
    _mock_find_job: AsyncMock,
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, 6101)
    source_sha = "c" * 64
    track = await _make_telegram_track(
        db_session,
        user_id=user.id,
        blob_sha=source_sha,
    )

    service = TelegramImportBackfillService(db_session)
    report = await service.run(limit=10, dry_run=False)

    assert report.dry_run is False
    assert report.enqueued == 1
    assert report.failed == 0
    assert report.items[0].status == "enqueued"
    tmp_key = report.items[0].tmp_key
    assert tmp_key is not None
    assert tmp_key.startswith("tmp-transcode/")
    assert tmp_key.endswith(".ogg")
    mock_download.assert_awaited_once_with("blobs/aa/raw.ogg")
    mock_upload.assert_awaited_once_with(tmp_key, b"raw-ogg", "audio/ogg")
    mock_repair_kiq.assert_awaited_once()
    kiq_kwargs = mock_repair_kiq.await_args.kwargs
    assert kiq_kwargs["track_id"] == track.id
    assert kiq_kwargs["raw_key"] == tmp_key
    assert kiq_kwargs["feature_version"] == "ugc-playback-normalize-v1"
    mock_reindex.assert_awaited_once_with(track.id)

    await db_session.refresh(track)
    assert track.source_sha256 == source_sha


@patch(f"{_MOD}.q.find_existing_job", new_callable=AsyncMock, return_value=None)
@patch(f"{_MOD}._source_object_exists", new_callable=AsyncMock, return_value=True)
@patch(f"{_MOD}._is_marked_unrecoverable", new_callable=AsyncMock, return_value=False)
@patch(f"{_MOD}._acquire_schedule_cooldown", new_callable=AsyncMock, return_value=True)
@patch(
    "app.services.search_index_notify.schedule_reindex_track",
    new_callable=AsyncMock,
)
@patch(
    f"{_MOD}.repair_ugc_playback_normalize_task.kiq",
    new_callable=AsyncMock,
)
@patch(f"{_MOD}.s3.upload_object", new_callable=AsyncMock)
@patch(
    f"{_MOD}.s3.download_object",
    new_callable=AsyncMock,
    return_value=b"raw-ogg",
)
async def test_urgent_apply_queues_high_priority_repair(
    _mock_download: AsyncMock,
    _mock_upload: AsyncMock,
    mock_repair_kiq: AsyncMock,
    _mock_reindex: AsyncMock,
    _mock_cooldown: AsyncMock,
    _mock_unrec: AsyncMock,
    _mock_exists: AsyncMock,
    _mock_find_job: AsyncMock,
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, 6103)
    track = await _make_telegram_track(
        db_session,
        user_id=user.id,
    )

    service = TelegramImportBackfillService(db_session)
    report = await service.run(limit=10, dry_run=False, urgent=True)

    assert report.enqueued == 1
    kwargs = mock_repair_kiq.await_args.kwargs
    assert kwargs["track_id"] == track.id
    assert kwargs["priority"] == 0
    assert kwargs["feature_version"] == "ugc-playback-normalize-urgent-v1"


@patch(f"{_MOD}.q.find_existing_job", new_callable=AsyncMock, return_value=None)
@patch(f"{_MOD}._source_object_exists", new_callable=AsyncMock, return_value=True)
@patch(f"{_MOD}._is_marked_unrecoverable", new_callable=AsyncMock, return_value=False)
@patch(f"{_MOD}._acquire_schedule_cooldown", new_callable=AsyncMock, return_value=True)
@patch(
    "app.services.search_index_notify.schedule_reindex_track",
    new_callable=AsyncMock,
)
@patch(
    f"{_MOD}.repair_ugc_playback_normalize_task.kiq",
    new_callable=AsyncMock,
)
@patch(f"{_MOD}.s3.upload_object", new_callable=AsyncMock)
@patch(
    f"{_MOD}.s3.download_object",
    new_callable=AsyncMock,
    return_value=b"raw-ogg",
)
async def test_force_retry_uses_unique_feature_version(
    _mock_download: AsyncMock,
    _mock_upload: AsyncMock,
    mock_repair_kiq: AsyncMock,
    _mock_reindex: AsyncMock,
    _mock_cooldown: AsyncMock,
    _mock_unrec: AsyncMock,
    _mock_exists: AsyncMock,
    _mock_find_job: AsyncMock,
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, 6104)
    await _make_telegram_track(db_session, user_id=user.id)

    service = TelegramImportBackfillService(db_session)
    await service.run(
        limit=10, dry_run=False, urgent=True, force_retry=True
    )

    kwargs = mock_repair_kiq.await_args.kwargs
    feature_version = kwargs["feature_version"]
    assert feature_version.startswith(
        "ugc-playback-normalize-urgent-v1-retry-"
    )
    assert feature_version != "ugc-playback-normalize-urgent-v1"


@patch(f"{_MOD}.q.find_existing_job", new_callable=AsyncMock, return_value=None)
@patch(f"{_MOD}._source_object_exists", new_callable=AsyncMock, return_value=True)
@patch(f"{_MOD}._is_marked_unrecoverable", new_callable=AsyncMock, return_value=False)
@patch(f"{_MOD}._acquire_schedule_cooldown", new_callable=AsyncMock, return_value=True)
@patch(f"{_MOD}.s3.upload_object", new_callable=AsyncMock)
@patch(
    f"{_MOD}.s3.download_object",
    new_callable=AsyncMock,
    return_value=b"raw-bytes",
)
@patch(
    f"{_MOD}.repair_ugc_playback_normalize_task.kiq",
    new_callable=AsyncMock,
)
async def test_apply_hashes_source_when_blob_is_missing(
    mock_repair_kiq: AsyncMock,
    _mock_download: AsyncMock,
    _mock_upload: AsyncMock,
    _mock_cooldown: AsyncMock,
    _mock_unrec: AsyncMock,
    _mock_exists: AsyncMock,
    _mock_find_job: AsyncMock,
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, 6102)
    track = await _make_telegram_track(
        db_session,
        user_id=user.id,
        blob_sha=None,
    )

    service = TelegramImportBackfillService(db_session)
    await service.run(limit=10, dry_run=False)

    kwargs = mock_repair_kiq.await_args.kwargs
    assert kwargs["track_id"] == track.id
    assert kwargs["source_sha256"] == (
        "48c2a3cc55bca79baff97910b96c74b906fc5d893a1bc5ccd14d629d"
        "3f3ef715"
    )
    assert kwargs["feature_version"] == "ugc-playback-normalize-v1"
