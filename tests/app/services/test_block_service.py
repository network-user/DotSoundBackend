import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user import UserRepository
from app.services.block_service import BlockService

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int,
) -> int:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        telegram_id, f"u{telegram_id}", "T", None
    )
    return user.id


async def test_block_user(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 900)
    u2 = await _make_user(session, 901)

    svc = BlockService(session)
    await svc.block_user(u1, u2)

    assert await svc.is_blocked(u1, u2) is True


async def test_block_self_raises(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 902)
    svc = BlockService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.block_user(u1, u1)

    assert exc.value.status_code == 400


async def test_block_idempotent(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 903)
    u2 = await _make_user(session, 904)

    svc = BlockService(session)
    await svc.block_user(u1, u2)
    await svc.block_user(u1, u2)

    assert await svc.is_blocked(u1, u2) is True


async def test_unblock_user(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 905)
    u2 = await _make_user(session, 906)

    svc = BlockService(session)
    await svc.block_user(u1, u2)
    await svc.unblock_user(u1, u2)

    assert await svc.is_blocked(u1, u2) is False


async def test_get_blocked_users(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 907)
    u2 = await _make_user(session, 908)
    u3 = await _make_user(session, 909)

    svc = BlockService(session)
    await svc.block_user(u1, u2)
    await svc.block_user(u1, u3)

    blocked = await svc.get_blocked_users(u1)

    assert set(blocked) == {u2, u3}


async def test_is_blocked_false(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 910)
    u2 = await _make_user(session, 911)

    svc = BlockService(session)

    assert await svc.is_blocked(u1, u2) is False
