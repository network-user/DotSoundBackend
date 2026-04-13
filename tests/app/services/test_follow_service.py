import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user import UserRepository
from app.services.follow_service import FollowService

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int,
) -> int:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        telegram_id, f"u{telegram_id}", "Test", None
    )
    return user.id


async def test_toggle_follow(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 300)
    u2 = await _make_user(session, 301)

    svc = FollowService(session)
    result = await svc.toggle(u1, u2)

    assert result is True


async def test_toggle_unfollow(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 302)
    u2 = await _make_user(session, 303)

    svc = FollowService(session)
    await svc.toggle(u1, u2)
    result = await svc.toggle(u1, u2)

    assert result is False


async def test_toggle_follow_self_raises(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 304)
    svc = FollowService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.toggle(u1, u1)

    assert exc.value.status_code == 400


async def test_is_following(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 305)
    u2 = await _make_user(session, 306)

    svc = FollowService(session)
    assert await svc.is_following(u1, u2) is False

    await svc.toggle(u1, u2)
    assert await svc.is_following(u1, u2) is True


async def test_list_followers(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 307)
    u2 = await _make_user(session, 308)

    svc = FollowService(session)
    await svc.toggle(u1, u2)

    followers, total = await svc.list_followers(u2)

    assert total == 1
    assert followers[0].id == u1


async def test_list_following(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 309)
    u2 = await _make_user(session, 310)

    svc = FollowService(session)
    await svc.toggle(u1, u2)

    following, total = await svc.list_following(u1)

    assert total == 1
    assert following[0].id == u2


async def test_toggle_follow_user_not_found(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 311)
    svc = FollowService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.toggle(u1, 9999)

    assert exc.value.status_code == 404
