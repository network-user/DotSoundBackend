from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.like import Like
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.like_service import LikeService

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 200,
) -> int:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        telegram_id, "qu", "QueueUser", None
    )
    return user.id


async def _seed_liked(
    session: AsyncSession,
    user_id: int,
    titles: list[str],
    base_time: datetime,
) -> list[int]:
    """Create N tracks and seed Like rows with strictly
    increasing created_at so sort=oldest gives titles[0] first."""
    tr_repo = TrackRepository(session)
    ids: list[int] = []
    for i, t in enumerate(titles):
        tr = await tr_repo.create(
            title=t, file_key=f"k{i}", uploaded_by_id=user_id
        )
        ids.append(tr.id)
        session.add(
            Like(
                user_id=user_id,
                track_id=tr.id,
                created_at=base_time + timedelta(minutes=i),
            )
        )
    await session.flush()
    return ids


async def test_list_liked_oldest_display_order(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    ids = await _seed_liked(
        session, uid, ["t1", "t2", "t3", "t4", "t5"], base
    )

    svc = LikeService(session)
    rows, total = await svc.list_liked(uid, sort_order="oldest")

    assert total == 5
    # oldest first => ids in insertion order
    assert [r[0].id for r in rows] == ids


async def test_list_liked_queue_oldest_returns_strictly_newer(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    ids = await _seed_liked(
        session, uid, ["t1", "t2", "t3", "t4", "t5"], base
    )

    svc = LikeService(session)
    # User clicks t3 in oldest sort. Expected next queue: [t4, t5].
    next_tracks = await svc.list_liked_queue(
        user_id=uid,
        current_track_id=ids[2],
        size=10,
        sort_order="oldest",
    )

    assert [t.id for t in next_tracks] == [ids[3], ids[4]]


async def test_list_liked_queue_oldest_first_track(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    ids = await _seed_liked(
        session, uid, ["t1", "t2", "t3"], base
    )

    svc = LikeService(session)
    next_tracks = await svc.list_liked_queue(
        user_id=uid,
        current_track_id=ids[0],
        size=10,
        sort_order="oldest",
    )
    assert [t.id for t in next_tracks] == [ids[1], ids[2]]


async def test_list_liked_queue_oldest_last_track(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    ids = await _seed_liked(
        session, uid, ["t1", "t2", "t3"], base
    )

    svc = LikeService(session)
    next_tracks = await svc.list_liked_queue(
        user_id=uid,
        current_track_id=ids[-1],
        size=10,
        sort_order="oldest",
    )
    assert [t.id for t in next_tracks] == []


async def test_list_liked_queue_newest_returns_strictly_older(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    ids = await _seed_liked(
        session, uid, ["t1", "t2", "t3", "t4", "t5"], base
    )

    svc = LikeService(session)
    # Newest sort displays t5..t1. Click t3 => expect [t2, t1].
    next_tracks = await svc.list_liked_queue(
        user_id=uid,
        current_track_id=ids[2],
        size=10,
        sort_order="newest",
    )
    assert [t.id for t in next_tracks] == [ids[1], ids[0]]
