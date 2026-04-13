import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.like_service import LikeService

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 100,
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


async def test_toggle_like_adds(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LikeService(session)
    result = await svc.toggle(uid, tid)

    assert result is True


async def test_toggle_like_removes(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LikeService(session)
    await svc.toggle(uid, tid)
    result = await svc.toggle(uid, tid)

    assert result is False


async def test_toggle_like_user_not_found(
    session: AsyncSession,
) -> None:
    svc = LikeService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.toggle(9999, 1)

    assert exc.value.status_code == 404


async def test_toggle_like_track_not_found(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = LikeService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.toggle(uid, 9999)

    assert exc.value.status_code == 404


async def test_is_liked(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LikeService(session)
    assert await svc.is_liked(uid, tid) is False

    await svc.toggle(uid, tid)
    assert await svc.is_liked(uid, tid) is True


async def test_list_liked_empty(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = LikeService(session)

    tracks, total = await svc.list_liked(uid)

    assert tracks == []
    assert total == 0


async def test_list_liked_returns_liked_tracks(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LikeService(session)
    await svc.toggle(uid, tid)
    tracks, total = await svc.list_liked(uid)

    assert total >= 1
    assert any(t.id == tid for t in tracks)


async def test_list_liked_user_not_found(
    session: AsyncSession,
) -> None:
    svc = LikeService(session)

    tracks, total = await svc.list_liked(9999)

    assert tracks == []
    assert total == 0


async def test_toggle_like_removes_dislike(
    session: AsyncSession,
) -> None:
    from app.services.dislike_service import (
        DislikeService,
    )

    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    dsvc = DislikeService(session)
    await dsvc.toggle(uid, tid)
    assert await dsvc.is_disliked(uid, tid) is True

    svc = LikeService(session)
    await svc.toggle(uid, tid)

    assert await dsvc.is_disliked(uid, tid) is False
    assert await svc.is_liked(uid, tid) is True
