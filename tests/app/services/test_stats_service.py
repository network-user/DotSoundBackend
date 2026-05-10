import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.services.stats_service import StatsService

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 1600,
) -> User:
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
    owner_id: int,
    play_count: int = 0,
) -> Track:
    track = Track(
        title="T",
        file_key="k",
        uploaded_by_id=owner_id,
        play_count=play_count,
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return track


async def test_get_author_stats_no_tracks(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    svc = StatsService(session)

    stats = await svc.get_author_stats(user.id)

    assert stats.total_tracks == 0
    assert stats.total_plays == 0


async def test_get_author_stats_with_tracks(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    await _make_track(
        session, user.id, play_count=10
    )
    await _make_track(
        session, user.id, play_count=20
    )

    svc = StatsService(session)
    stats = await svc.get_author_stats(user.id)

    assert stats.total_tracks == 2
    assert stats.total_plays == 30


async def test_get_author_stats_user_not_found(
    session: AsyncSession,
) -> None:
    svc = StatsService(session)

    stats = await svc.get_author_stats(9999)

    assert stats.total_tracks == 0
    assert stats.total_plays == 0


async def test_get_author_stats_top_tracks(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    for i in range(7):
        await _make_track(
            session, user.id, play_count=i * 10
        )

    svc = StatsService(session)
    stats = await svc.get_author_stats(user.id)

    assert len(stats.top_tracks) <= 5
    assert stats.total_tracks == 7


async def test_get_author_stats_by_telegram_id(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 1601)
    await _make_track(
        session, user.id, play_count=5
    )

    svc = StatsService(session)
    stats = await svc.get_author_stats(
        user.telegram_id
    )

    assert stats.total_tracks == 1
    assert stats.total_plays == 5


async def _emit_listen(
    session: AsyncSession,
    user_id: int,
    track_id: int,
    *,
    completed: bool = True,
) -> None:
    from datetime import UTC, datetime

    from app.models.listen_event import ListenEvent

    session.add(
        ListenEvent(
            user_id=user_id,
            track_id=track_id,
            started_at=datetime.now(UTC),
            duration_listened_seconds=120,
            total_duration_seconds=180,
            last_position_seconds=0,
            completed=completed,
            skipped=False,
            source_context=None,
        )
    )
    await session.flush()


async def test_get_user_top_tracks_drops_low_listen_count(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 1700)
    quiet = await _make_track(session, user.id)
    loud = await _make_track(session, user.id)
    # one completed event for the quiet track, four for the loud one
    await _emit_listen(session, user.id, quiet.id)
    for _ in range(4):
        await _emit_listen(session, user.id, loud.id)

    svc = StatsService(session)
    tracks, window = await svc.get_user_top_tracks(
        user.id, window="30d"
    )
    ids = [t.id for t in tracks]

    assert window == "30d"
    assert loud.id in ids
    assert quiet.id not in ids


async def test_get_user_top_tracks_normalizes_window(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 1701)
    track = await _make_track(session, user.id)
    for _ in range(5):
        await _emit_listen(session, user.id, track.id)

    svc = StatsService(session)
    _, window = await svc.get_user_top_tracks(
        user.id, window="garbage"
    )
    assert window in {"7d", "30d", "90d", "all"}


async def test_get_user_top_genres_returns_genre_with_count(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 1702)
    track = Track(
        title="G",
        file_key="k",
        uploaded_by_id=user.id,
        play_count=0,
        genre="rock",
    )
    session.add(track)
    await session.flush()
    for _ in range(5):
        await _emit_listen(session, user.id, track.id)

    svc = StatsService(session)
    items, _ = await svc.get_user_top_genres(
        user.id, window="all"
    )
    assert items, "expected at least one genre"
    assert items[0][0] == "rock"
    assert items[0][1] >= 1


async def test_get_user_minutes_by_day_buckets(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 1703)
    track = await _make_track(session, user.id)
    for _ in range(3):
        await _emit_listen(session, user.id, track.id)

    svc = StatsService(session)
    rows = await svc.get_user_minutes_by_day(
        user.id, days=7
    )
    assert rows, "expected at least one bucket"
    # 3 listens of 120 sec each = 360 sec = 6 minutes,
    # likely all on the same UTC day, so one bucket of 6.
    total_minutes = sum(m for (_, m) in rows)
    assert total_minutes >= 6


async def test_get_user_minutes_by_day_clamps_days(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 1704)
    svc = StatsService(session)
    # ridiculously large value should be clamped to 90;
    # zero/negative should be clamped to 1. We only verify
    # the call does not raise.
    rows1 = await svc.get_user_minutes_by_day(
        user.id, days=10_000
    )
    rows2 = await svc.get_user_minutes_by_day(
        user.id, days=-5
    )
    assert isinstance(rows1, list)
    assert isinstance(rows2, list)
