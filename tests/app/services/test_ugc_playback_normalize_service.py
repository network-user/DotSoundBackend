from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio_blob import AudioBlob
from app.models.track import Track
from app.models.user import User
from app.services.ugc_playback_normalize_service import (
    UgcPlaybackNormalizeService,
    track_needs_ugc_playback_normalize,
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


async def _make_track(
    session: AsyncSession,
    *,
    user_id: int,
    source: str = "internal",
    file_key: str = "temp/raw/legacy_1.mp3",
    hls_manifest_key: str | None = None,
) -> Track:
    track = Track(
        title="Song",
        artist="A",
        file_key=file_key,
        hls_manifest_key=hls_manifest_key,
        uploaded_by_id=user_id,
        is_active=True,
        is_public=True,
        source=source,
        catalog_type="ugc",
        access_mode="internal_stream",
        processing_status="error",
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return track


def test_track_needs_normalize_manual_upload() -> None:
    track = Track(
        title="T",
        file_key="temp/uploads/1/uuid/song.mp3",
        source="internal",
        catalog_type="ugc",
        access_mode="internal_stream",
        is_active=True,
    )
    assert track_needs_ugc_playback_normalize(track) is True


@patch(f"{_MOD}.repair_ugc_playback_normalize_task.kiq", new_callable=AsyncMock)
@patch(f"{_MOD}.s3.upload_object", new_callable=AsyncMock)
@patch(f"{_MOD}.s3.download_object", new_callable=AsyncMock, return_value=b"raw")
@patch(
    f"{_MOD}._acquire_schedule_cooldown",
    new_callable=AsyncMock,
    side_effect=[True, False],
)
@patch(f"{_MOD}._is_marked_unrecoverable", new_callable=AsyncMock, return_value=False)
@patch(f"{_MOD}._source_object_exists", new_callable=AsyncMock, return_value=True)
@patch(f"{_MOD}.q.find_existing_job", new_callable=AsyncMock, return_value=None)
async def test_schedule_on_playback_enqueues_once(
    _find_job: AsyncMock,
    _exists: AsyncMock,
    _unrec: AsyncMock,
    _cooldown: AsyncMock,
    _download: AsyncMock,
    _upload: AsyncMock,
    mock_kiq: AsyncMock,
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, 7200)
    track = await _make_track(db_session, user_id=user.id)

    svc = UgcPlaybackNormalizeService(db_session)
    first = await svc.try_schedule_for_track(track, trigger="playback")
    second = await svc.try_schedule_for_track(track, trigger="playback")

    assert first.action == "enqueued"
    assert second.action == "cooldown"
    mock_kiq.assert_awaited_once()


@patch(f"{_MOD}._is_marked_unrecoverable", new_callable=AsyncMock, return_value=False)
@patch(f"{_MOD}._source_object_exists", new_callable=AsyncMock, return_value=False)
async def test_schedule_marks_missing_source_unrecoverable(
    _exists: AsyncMock,
    _unrec: AsyncMock,
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, 7201)
    track = await _make_track(db_session, user_id=user.id)

    svc = UgcPlaybackNormalizeService(db_session)
    result = await svc.try_schedule_for_track(track, trigger="playback")

    assert result.action == "unrecoverable"
