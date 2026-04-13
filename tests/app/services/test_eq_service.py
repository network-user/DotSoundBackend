import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.eq_service import EqService

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 1500,
) -> int:
    user = User(
        telegram_id=telegram_id,
        username=f"u{telegram_id}",
        first_name="T",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user.id


async def test_get_settings_default(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = EqService(session)

    result = await svc.get_settings(uid)

    assert result.preset == "Flat"
    assert result.bands == [0, 0, 0, 0, 0, 0, 0, 0]


async def test_save_settings(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = EqService(session)
    bands = [1.0, 2.0, 3.0, 0, 0, 0, 0, 0]

    result = await svc.save_settings(
        uid, "Bass Boost", bands
    )

    assert result.preset == "Bass Boost"
    assert result.bands == bands


async def test_save_settings_updates_existing(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = EqService(session)
    bands1 = [1.0] * 8
    await svc.save_settings(uid, "P1", bands1)

    bands2 = [2.0] * 8
    result = await svc.save_settings(
        uid, "P2", bands2
    )

    assert result.preset == "P2"
    assert result.bands == bands2


async def test_get_settings_after_save(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = EqService(session)
    bands = [3.0, 0, 0, 0, 0, 0, 0, -3.0]
    await svc.save_settings(uid, "Custom", bands)

    result = await svc.get_settings(uid)

    assert result.preset == "Custom"
    assert result.bands[0] == 3.0
    assert result.bands[7] == -3.0
