import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.like import LikeRepository
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
    repo = LikeRepository(session)

    like = await repo.add(user.id, track.id)
    assert like.user_id == user.id

    found = await repo.get(user.id, track.id)
    assert found is not None


async def test_remove(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = LikeRepository(session)
    await repo.add(user.id, track.id)

    removed = await repo.remove(user.id, track.id)
    assert removed is True

    removed_again = await repo.remove(
        user.id, track.id
    )
    assert removed_again is False


async def test_list_liked_tracks_empty(
    session: AsyncSession,
) -> None:
    user, _ = await _seed(session)
    repo = LikeRepository(session)

    tracks, total = await repo.list_liked_tracks(
        user.id
    )
    assert total == 0
    assert tracks == []


async def test_list_liked_tracks_with_data(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = LikeRepository(session)
    await repo.add(user.id, track.id)

    tracks, total = await repo.list_liked_tracks(
        user.id
    )
    assert total == 1
    assert tracks[0].id == track.id
