from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.track_playback_failure_event import TrackPlaybackFailureEvent
from app.models.user import User
from app.repositories.track import TrackRepository
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
    assert track.playback_last_checked_at is not None
    assert track.playback_last_repair_attempt_at is not None


async def test_repair_track_marks_unresolved_soundcloud_as_suppressed(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    track = await _make_failed_soundcloud_track(db_session, user)

    resolve = AsyncMock(
        side_effect=HTTPException(
            status_code=502,
            detail="SoundCloud stream unavailable",
        )
    )

    with (
        patch(f"{_MOD}._resolve_third_party_stream", new=resolve),
        patch(
            "app.services.track_fallback_service."
            "TrackFallbackService.try_refresh_sc_url",
            new=AsyncMock(return_value=False),
        ),
    ):
        result = await TrackPlaybackRepairService(db_session).repair_track(
            track.id,
        )

    assert result["ok"] is False
    assert result["status"] == "unresolved"
    assert result["suppressed"] is True
    assert track.is_active is True
    assert track.playback_last_checked_at is not None
    assert track.playback_last_repair_attempt_at is not None
    assert track.playback_last_failure_source == (
        "scheduled_playback_audit_failed"
    )
    assert track.playback_suppressed_until is not None

    rows = (
        await db_session.execute(
            select(TrackPlaybackFailureEvent).where(
                TrackPlaybackFailureEvent.track_id == track.id
            )
        )
    ).scalars().all()
    assert rows[-1].source == "scheduled_playback_audit_failed"


async def test_repair_track_healthy_source_records_check_timestamp(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    track = Track(
        title="Healthy",
        access_mode="third_party_stream",
        catalog_type="external_reference",
        source="soundcloud",
        source_platform="soundcloud",
        sc_url="https://soundcloud.com/a/healthy",
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
    )
    db_session.add(track)
    await db_session.flush()
    await db_session.refresh(track)

    with patch(
        f"{_MOD}._resolve_third_party_stream",
        new=AsyncMock(return_value=("https://cdn/audio.m3u8", "hls")),
    ):
        result = await TrackPlaybackRepairService(db_session).repair_track(
            track.id,
        )

    assert result["ok"] is True
    assert result["refreshed_sc_url"] is False
    assert track.playback_last_checked_at is not None
    assert track.playback_last_repair_attempt_at is None


async def test_repair_candidates_audits_public_soundcloud_scope(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    failed = await _make_failed_soundcloud_track(db_session, user)
    now = datetime.now(UTC)
    healthy = Track(
        title="Healthy",
        access_mode="third_party_stream",
        catalog_type="external_reference",
        source_platform="soundcloud",
        sc_url="https://soundcloud.com/a/healthy",
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
    )
    recently_checked = Track(
        title="Recently Checked",
        access_mode="third_party_stream",
        catalog_type="external_reference",
        source_platform="soundcloud",
        sc_url="https://soundcloud.com/a/recent",
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
        playback_last_checked_at=now,
    )
    private = Track(
        title="Private",
        access_mode="third_party_stream",
        catalog_type="external_reference",
        source_platform="soundcloud",
        sc_url="https://soundcloud.com/a/private",
        is_active=True,
        is_public=False,
        uploaded_by_id=user.id,
    )
    bandcamp = Track(
        title="Bandcamp",
        access_mode="third_party_stream",
        catalog_type="external_reference",
        source_platform="bandcamp",
        source_url="https://bandcamp.example/track",
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
    )
    db_session.add_all([healthy, recently_checked, private, bandcamp])
    await db_session.flush()

    with patch.object(
        TrackPlaybackRepairService,
        "repair_track",
        new=AsyncMock(return_value={"ok": True}),
    ) as repair:
        result = await TrackPlaybackRepairService(
            db_session,
        ).repair_candidates(10)

    assert result["inspected"] == 3
    assert result["repaired"] == 3
    assert [call.args[0] for call in repair.await_args_list] == [
        failed.id,
        healthy.id,
        recently_checked.id,
    ]


async def test_soundcloud_repair_candidate_order_prioritizes_audit_state(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    failed = await _make_failed_soundcloud_track(db_session, user)
    now = datetime.now(UTC)
    checked_old = Track(
        title="Checked Old",
        access_mode="third_party_stream",
        catalog_type="external_reference",
        source_platform="soundcloud",
        sc_url="https://soundcloud.com/a/old-check",
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
        playback_last_checked_at=now - timedelta(days=2),
    )
    checked_recent = Track(
        title="Checked Recent",
        access_mode="third_party_stream",
        catalog_type="external_reference",
        source_platform="soundcloud",
        sc_url="https://soundcloud.com/a/recent-check",
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
        playback_last_checked_at=now - timedelta(hours=1),
    )
    never_checked = Track(
        title="Never Checked",
        access_mode="third_party_stream",
        catalog_type="external_reference",
        source_platform="soundcloud",
        sc_url="https://soundcloud.com/a/never",
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
    )
    db_session.add_all([checked_old, checked_recent, never_checked])
    await db_session.flush()

    rows = await TrackRepository(
        db_session,
    ).list_soundcloud_playback_repair_candidates(limit=10)

    assert [row.id for row in rows] == [
        failed.id,
        never_checked.id,
        checked_old.id,
        checked_recent.id,
    ]
