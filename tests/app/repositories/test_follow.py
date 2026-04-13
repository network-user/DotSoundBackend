import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.follow import FollowRepository

pytestmark = pytest.mark.anyio


async def _make_users(session: AsyncSession):
    repo: BaseRepository[User] = BaseRepository(
        session, User
    )
    u1 = await repo.create(
        telegram_id=1,
        first_name="A",
        auth_provider="telegram",
    )
    u2 = await repo.create(
        telegram_id=2,
        first_name="B",
        auth_provider="telegram",
    )
    return u1, u2


async def test_add_and_remove(
    session: AsyncSession,
) -> None:
    u1, u2 = await _make_users(session)
    repo = FollowRepository(session)

    follow = await repo.add(u1.id, u2.id)
    assert follow.follower_id == u1.id

    removed = await repo.remove(u1.id, u2.id)
    assert removed is True

    removed_again = await repo.remove(u1.id, u2.id)
    assert removed_again is False


async def test_list_followers(
    session: AsyncSession,
) -> None:
    u1, u2 = await _make_users(session)
    repo = FollowRepository(session)
    await repo.add(u1.id, u2.id)

    followers, total = await repo.list_followers(
        u2.id
    )
    assert total == 1
    assert followers[0].id == u1.id


async def test_list_following(
    session: AsyncSession,
) -> None:
    u1, u2 = await _make_users(session)
    repo = FollowRepository(session)
    await repo.add(u1.id, u2.id)

    following, total = await repo.list_following(
        u1.id
    )
    assert total == 1
    assert following[0].id == u2.id


async def test_count_followers_and_following(
    session: AsyncSession,
) -> None:
    u1, u2 = await _make_users(session)
    repo = FollowRepository(session)

    assert await repo.count_followers(u2.id) == 0
    assert await repo.count_following(u1.id) == 0

    await repo.add(u1.id, u2.id)
    assert await repo.count_followers(u2.id) == 1
    assert await repo.count_following(u1.id) == 1
