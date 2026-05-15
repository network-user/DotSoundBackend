from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.services.playback_repair_worker import TrackPlaybackRepairService

pytestmark = pytest.mark.anyio

_MOD = "app.services.playback_repair_worker"


async def _make_user(session: AsyncSession) -> User:
    user = User(telegram_id=9300, first_name="Repair")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _make_failed_soundcloud_track(
    session: AsyncSession,
    user: User,
) -> Track:
    now = datetime.now(UTC)
    track = Track(
        title="Broken",
        artist="Artist",
        duration_seconds=180,
        access_mode="third_party_stream",
        catalog_type="external_reference",
        source="soundcloud",
        source_platform="soundcloud",
        sc_url="https://soundcloud.com/a/old",
        source_url="https://soundcloud.com/a/old",
        canonical_source_url="https://soundcloud.com/a/old",
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
        playback_last_failure_at=now,
        playback_last_http_status=502,
        playback_last_failure_source="server_recovery_exhausted",
        playback_recovery_failed_at=now,
        playback_suppressed_until=now + timedelta(days=1),
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return track


async def test_repair_track_refreshes_soundcloud_url_and_clears_health(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    track = await _make_failed_soundcloud_track(db_session, user)

    async def fake_refresh(_self: object, tr: Track) -> bool:
        tr.sc_url = "https://soundcloud.com/a/new"
        tr.source_url = tr.sc_url
        tr.canonical_source_url = tr.sc_url
        return True

    resolve = AsyncMock(
        side_effect=[
            HTTPException(
                status_code=502, detail="SoundCloud stream unavailable"
            ),
            ("https://cdn/audio.mp3", "progressive"),
        ]
    )

    with (
        patch(f"{_MOD}._resolve_third_party_stream", new=resolve),
        patch(
            "app.services.track_fallback_service."
            "TrackFallbackService.try_refresh_sc_url",
            new=fake_refresh,
        ),
    ):
        result = await TrackPlaybackRepairService(db_session).repair_track(
            track.id,
        )

    assert result["ok"] is True
    assert result["refreshed_sc_url"] is True
    assert result["sc_url_changed"] is True
    assert track.sc_url == "https://soundcloud.com/a/new"
    assert track.playback_last_failure_at is None
    assert track.playback_last_http_status is None
    assert track.playback_last_failure_source is None
    assert track.playback_recovery_failed_at is None
    assert track.playback_suppressed_until is None


async def test_repair_candidates_uses_soundcloud_failure_scope(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    failed = await _make_failed_soundcloud_track(db_session, user)
    healthy = Track(
        title="Healthy",
        access_mode="third_party_stream",
        source_platform="soundcloud",
        sc_url="https://soundcloud.com/a/healthy",
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
    )
    db_session.add(healthy)
    await db_session.flush()

    with patch.object(
        TrackPlaybackRepairService,
        "repair_track",
        new=AsyncMock(return_value={"ok": True}),
    ) as repair:
        result = await TrackPlaybackRepairService(
            db_session,
        ).repair_candidates(10)

    assert result["inspected"] == 1
    assert result["repaired"] == 1
    repair.assert_awaited_once_with(failed.id)
