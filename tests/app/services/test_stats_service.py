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
