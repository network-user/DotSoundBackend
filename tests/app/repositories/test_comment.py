import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.comment import CommentRepository
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


async def test_create_comment(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = CommentRepository(session)

    comment = await repo.create(
        track_id=track.id,
        user_id=user.id,
        text="Great song!",
    )
    assert comment.id is not None
    assert comment.text == "Great song!"


async def test_list_comments(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = CommentRepository(session)
    await repo.create(
        track_id=track.id,
        user_id=user.id,
        text="First",
    )
    await repo.create(
        track_id=track.id,
        user_id=user.id,
        text="Second",
    )

    comments = await repo.list_root_comments(
        track.id, user.id, None, 50
    )
    assert len(comments) == 2


async def test_soft_delete(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = CommentRepository(session)
    comment = await repo.create(
        track_id=track.id,
        user_id=user.id,
        text="Delete me",
    )

    await repo.soft_delete(comment.id)
    await session.refresh(comment)
    assert comment.is_deleted is True

    visible = await repo.list_root_comments(
        track.id, user.id, None, 50
    )
    assert len(visible) == 0
