import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.album import AlbumRepository
from app.repositories.base import BaseRepository

pytestmark = pytest.mark.anyio


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


async def test_create_album(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = AlbumRepository(session)

    album = await repo.create(
        owner_id=user.id,
        title="Album 1",
        description="Desc",
    )

    assert album.id is not None
    assert album.title == "Album 1"


async def test_get_by_id(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = AlbumRepository(session)
    album = await repo.create(
        owner_id=user.id, title="X"
    )

    found = await repo.get_by_id(album.id)
    assert found is not None
    assert found.title == "X"

    missing = await repo.get_by_id(9999)
    assert missing is None


async def test_update_album(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = AlbumRepository(session)
    album = await repo.create(
        owner_id=user.id, title="Old"
    )

    updated = await repo.update(
        album, title="New", is_public=False
    )

    assert updated.title == "New"
    assert updated.is_public is False


async def test_list_by_user(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = AlbumRepository(session)
    await repo.create(
        owner_id=user.id, title="A1"
    )
    await repo.create(
        owner_id=user.id, title="A2"
    )

    albums, total = await repo.list_by_user(user.id)
    assert total == 2
    assert len(albums) == 2
