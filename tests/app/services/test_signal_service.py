import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.signal_service import (
    SignalService,
)

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 500,
) -> int:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        telegram_id, "u", "Test", None
    )
    return user.id


async def _make_track(
    session: AsyncSession,
    owner_id: int | None = None,
) -> int:
    repo = TrackRepository(session)
    track = await repo.create(
        title="T",
        file_key="k",
        uploaded_by_id=owner_id,
    )
    return track.id


async def test_record_listen(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid = await _make_track(db_session, uid)

    svc = SignalService(db_session)
    await svc.record_listen(
        user_id=uid,
        track_id=tid,
        duration_listened=120,
        total_duration=200,
        source_context="home",
    )

    count = await svc.get_listen_count(uid)
    assert count == 1


async def test_record_listen_completed(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid = await _make_track(db_session, uid)

    svc = SignalService(db_session)
    await svc.record_listen(
        user_id=uid,
        track_id=tid,
        duration_listened=180,
        total_duration=200,
    )

    events = await svc.get_recent_listens(uid)
    assert len(events) == 1
    assert events[0].completed is True
    assert events[0].skipped is False


async def test_record_listen_skipped(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid = await _make_track(db_session, uid)

    svc = SignalService(db_session)
    await svc.record_listen(
        user_id=uid,
        track_id=tid,
        duration_listened=5,
        total_duration=200,
    )

    events = await svc.get_recent_listens(uid)
    assert events[0].skipped is True
    assert events[0].completed is False


async def test_record_search_click(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid = await _make_track(db_session, uid)

    svc = SignalService(db_session)
    await svc.record_search_click(
        user_id=uid,
        query="test query",
        results_count=5,
        clicked_track_id=tid,
    )


async def test_multiple_listens(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid = await _make_track(db_session, uid)

    svc = SignalService(db_session)
    for _ in range(5):
        await svc.record_listen(
            user_id=uid,
            track_id=tid,
            duration_listened=100,
            total_duration=200,
        )

    count = await svc.get_listen_count(uid)
    assert count == 5
