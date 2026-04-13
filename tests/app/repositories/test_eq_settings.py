import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.eq_settings import (
    EqSettingsRepository,
)

pytestmark = pytest.mark.anyio

_DEFAULT_BANDS = [
    {"freq": 60, "gain": 0},
    {"freq": 230, "gain": 0},
    {"freq": 910, "gain": 0},
]


async def _make_user(
    session: AsyncSession,
) -> User:
    repo: BaseRepository[User] = BaseRepository(
        session, User
    )
    return await repo.create(
        telegram_id=1,
        first_name="U",
        auth_provider="telegram",
    )


async def test_get_by_user_id_not_found(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = EqSettingsRepository(session)

    result = await repo.get_by_user_id(user.id)
    assert result is None


async def test_create_and_get(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = EqSettingsRepository(session)

    settings = await repo.create(
        user_id=user.id,
        bands=_DEFAULT_BANDS,
        preset="flat",
    )
    assert settings.id is not None
    assert settings.bands == _DEFAULT_BANDS

    found = await repo.get_by_user_id(user.id)
    assert found is not None
    assert found.preset == "flat"


async def test_count(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = EqSettingsRepository(session)

    assert await repo.count() == 0

    await repo.create(
        user_id=user.id,
        bands=_DEFAULT_BANDS,
    )
    assert await repo.count() == 1
