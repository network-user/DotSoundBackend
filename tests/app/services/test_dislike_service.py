import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.dislike_service import DislikeService
from app.services.like_service import LikeService

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 200,
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
        title="T", file_key="k",
        uploaded_by_id=owner_id,
    )
    return track.id


async def test_toggle_dislike_adds(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = DislikeService(session)
    disliked, _ids = await svc.toggle(uid, tid)

    assert disliked is True


async def test_toggle_dislike_removes(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = DislikeService(session)
    await svc.toggle(uid, tid)
    disliked, _ids = await svc.toggle(uid, tid)

    assert disliked is False


async def test_toggle_dislike_user_not_found(
    session: AsyncSession,
) -> None:
    svc = DislikeService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.toggle(9999, 1)

    assert exc.value.status_code == 404


async def test_toggle_dislike_track_not_found(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = DislikeService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.toggle(uid, 9999)

    assert exc.value.status_code == 404


async def test_is_disliked(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = DislikeService(session)
    assert await svc.is_disliked(uid, tid) is False

    await svc.toggle(uid, tid)
    assert await svc.is_disliked(uid, tid) is True


async def test_list_disliked(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = DislikeService(session)
    rows, total = await svc.list_disliked(uid)
    assert rows == []
    assert total == 0

    await svc.toggle(uid, tid)
    rows, total = await svc.list_disliked(uid)

    assert total == 1
    assert len(rows) == 1
    assert rows[0][0].id == tid


async def test_toggle_dislike_removes_like(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    like_svc = LikeService(session)
    await like_svc.toggle(uid, tid)
    assert await like_svc.is_liked(uid, tid) is True

    svc = DislikeService(session)
    await svc.toggle(uid, tid)

    assert await like_svc.is_liked(uid, tid) is False
    assert await svc.is_disliked(uid, tid) is True
