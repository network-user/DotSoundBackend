import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.dislike import DislikeRepository
from app.repositories.track import TrackRepository

pytestmark = pytest.mark.anyio


async def _seed(session: AsyncSession):
    user_repo: BaseRepository[User] = BaseRepository(
        session, User
    )
    user = await user_repo.create(
        telegram_id=1,
        first_name="U",
        auth_provider="telegram",
    )
    track_repo = TrackRepository(session)
    track = await track_repo.create(
        title="T",
        artist="A",
        uploaded_by_id=user.id,
    )
    return user, track


async def test_add_and_get(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = DislikeRepository(session)

    dislike = await repo.add(user.id, track.id)
    assert dislike.user_id == user.id

    found = await repo.get(user.id, track.id)
    assert found is not None


async def test_remove(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = DislikeRepository(session)
    await repo.add(user.id, track.id)

    removed = await repo.remove(user.id, track.id)
    assert removed is True

    removed_again = await repo.remove(
        user.id, track.id
    )
    assert removed_again is False


async def test_get_not_found(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = DislikeRepository(session)

    result = await repo.get(user.id, track.id)
    assert result is None
