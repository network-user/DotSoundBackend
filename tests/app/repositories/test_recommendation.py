from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listen_event import ListenEvent
from app.models.playlist import Playlist, PlaylistTrack
from app.repositories.recommendation import (
    RecommendationRepository,
)

pytestmark = pytest.mark.anyio


async def _add_listen(
    session: AsyncSession,
    *,
    user_id: int,
    track_id: int,
    duration_listened_seconds: int,
    total_duration_seconds: int,
    completed: bool,
    skipped: bool,
    age_days: float = 1.0,
) -> ListenEvent:
    started = datetime.now(UTC) - timedelta(days=age_days)
    event = ListenEvent(
        user_id=user_id,
        track_id=track_id,
        started_at=started,
        duration_listened_seconds=duration_listened_seconds,
        total_duration_seconds=total_duration_seconds,
        last_position_seconds=duration_listened_seconds,
        completed=completed,
        skipped=skipped,
        source_context="test",
        created_at=started,
    )
    session.add(event)
    await session.flush()
    return event


async def test_get_recent_listen_events_returns_within_window(
    session: AsyncSession,
    create_user,
    create_track,
) -> None:
    user = await create_user()
    track = await create_track()
    await _add_listen(
        session,
        user_id=user.id,
        track_id=track.id,
        duration_listened_seconds=120,
        total_duration_seconds=200,
        completed=False,
        skipped=False,
        age_days=1.0,
    )
    await _add_listen(
        session,
        user_id=user.id,
        track_id=track.id,
        duration_listened_seconds=10,
        total_duration_seconds=200,
        completed=False,
        skipped=True,
        age_days=60.0,
    )

    repo = RecommendationRepository(session)
    events = await repo.get_recent_listen_events(user_id=user.id, days=30)
    assert len(events) == 1
    assert events[0].duration_listened_seconds == 120


async def test_get_repeat_listen_counts_only_qualified(
    session: AsyncSession,
    create_user,
    create_track,
) -> None:
    user = await create_user()
    track_a = await create_track()
    track_b = await create_track()

    for _ in range(3):
        await _add_listen(
            session,
            user_id=user.id,
            track_id=track_a.id,
            duration_listened_seconds=200,
            total_duration_seconds=200,
            completed=True,
            skipped=False,
        )
    for _ in range(2):
        await _add_listen(
            session,
            user_id=user.id,
            track_id=track_b.id,
            duration_listened_seconds=5,
            total_duration_seconds=200,
            completed=False,
            skipped=True,
        )

    repo = RecommendationRepository(session)
    counts = await repo.get_repeat_listen_counts(
        user_id=user.id, days=30, min_count=2
    )
    assert counts == {track_a.id: 3}


async def test_get_repeat_listen_counts_respects_min_count(
    session: AsyncSession,
    create_user,
    create_track,
) -> None:
    user = await create_user()
    track = await create_track()
    await _add_listen(
        session,
        user_id=user.id,
        track_id=track.id,
        duration_listened_seconds=200,
        total_duration_seconds=200,
        completed=True,
        skipped=False,
    )

    repo = RecommendationRepository(session)
    counts = await repo.get_repeat_listen_counts(
        user_id=user.id, days=30, min_count=2
    )
    assert counts == {}


async def test_get_unique_savers_per_track_counts_distinct_owners(
    session: AsyncSession,
    create_user,
    create_track,
) -> None:
    owner_a = await create_user()
    owner_b = await create_user()
    track = await create_track()

    for owner in (owner_a, owner_b):
        playlist = Playlist(name="p", owner_id=owner.id)
        session.add(playlist)
        await session.flush()
        session.add(PlaylistTrack(playlist_id=playlist.id, track_id=track.id))
        await session.flush()

    second_playlist = Playlist(name="p2", owner_id=owner_a.id)
    session.add(second_playlist)
    await session.flush()
    session.add(
        PlaylistTrack(playlist_id=second_playlist.id, track_id=track.id)
    )
    await session.flush()

    repo = RecommendationRepository(session)
    counts = await repo.get_unique_savers_per_track([track.id])
    assert counts == {track.id: 2}


async def test_get_unique_savers_empty_input(
    session: AsyncSession,
) -> None:
    repo = RecommendationRepository(session)
    assert await repo.get_unique_savers_per_track([]) == {}


async def test_get_unique_listeners_per_track_qualified_only(
    session: AsyncSession,
    create_user,
    create_track,
) -> None:
    listener_a = await create_user()
    listener_b = await create_user()
    track = await create_track()

    await _add_listen(
        session,
        user_id=listener_a.id,
        track_id=track.id,
        duration_listened_seconds=200,
        total_duration_seconds=200,
        completed=True,
        skipped=False,
    )
    await _add_listen(
        session,
        user_id=listener_a.id,
        track_id=track.id,
        duration_listened_seconds=200,
        total_duration_seconds=200,
        completed=True,
        skipped=False,
    )
    await _add_listen(
        session,
        user_id=listener_b.id,
        track_id=track.id,
        duration_listened_seconds=4,
        total_duration_seconds=200,
        completed=False,
        skipped=True,
    )

    repo = RecommendationRepository(session)
    counts = await repo.get_unique_listeners_per_track(
        track_ids=[track.id], days=30
    )
    assert counts == {track.id: 1}


async def test_get_unique_listeners_empty_input(
    session: AsyncSession,
) -> None:
    repo = RecommendationRepository(session)
    out = await repo.get_unique_listeners_per_track(track_ids=[], days=7)
    assert out == {}
