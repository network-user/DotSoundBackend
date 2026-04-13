import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository

pytestmark = pytest.mark.anyio


async def test_create_and_get_by_id(
    session: AsyncSession,
) -> None:
    repo: BaseRepository[User] = BaseRepository(
        session, User
    )
    user = await repo.create(
        telegram_id=1,
        first_name="Alice",
        auth_provider="telegram",
    )

    found = await repo.get_by_id(user.id)
    assert found is not None
    assert found.first_name == "Alice"


async def test_get_by_id_not_found(
    session: AsyncSession,
) -> None:
    repo: BaseRepository[User] = BaseRepository(
        session, User
    )

    result = await repo.get_by_id(999)
    assert result is None


async def test_delete(
    session: AsyncSession,
) -> None:
    repo: BaseRepository[User] = BaseRepository(
        session, User
    )
    user = await repo.create(
        telegram_id=2,
        first_name="Bob",
        auth_provider="telegram",
    )

    await repo.delete(user)
    assert await repo.get_by_id(user.id) is None


async def test_count(
    session: AsyncSession,
) -> None:
    repo: BaseRepository[User] = BaseRepository(
        session, User
    )
    assert await repo.count() == 0

    await repo.create(
        telegram_id=3,
        first_name="C",
        auth_provider="telegram",
    )
    await repo.create(
        telegram_id=4,
        first_name="D",
        auth_provider="telegram",
    )
    assert await repo.count() == 2
