import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.block import BlockRepository

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


async def test_block_and_check(
    session: AsyncSession,
) -> None:
    u1, u2 = await _make_users(session)
    repo = BlockRepository(session)

    assert (
        await repo.is_blocked(u1.id, u2.id)
        is False
    )

    block = await repo.block(u1.id, u2.id)
    assert block.blocker_id == u1.id

    assert (
        await repo.is_blocked(u1.id, u2.id) is True
    )
    assert (
        await repo.is_blocked(u2.id, u1.id) is True
    )


async def test_unblock(
    session: AsyncSession,
) -> None:
    u1, u2 = await _make_users(session)
    repo = BlockRepository(session)
    await repo.block(u1.id, u2.id)

    await repo.unblock(u1.id, u2.id)
    assert (
        await repo.is_blocked(u1.id, u2.id)
        is False
    )


async def test_get_blocked_users(
    session: AsyncSession,
) -> None:
    u1, u2 = await _make_users(session)
    repo = BlockRepository(session)

    assert await repo.get_blocked_users(u1.id) == []

    await repo.block(u1.id, u2.id)
    blocked = await repo.get_blocked_users(u1.id)
    assert blocked == [u2.id]
