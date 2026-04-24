import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.notification import (
    NotificationRepository,
)

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


async def test_create_notification(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = NotificationRepository(session)

    notif = await repo.create(
        user_id=user.id,
        type="like",
        title="New like",
        body="Someone liked your track",
    )
    assert notif.id is not None
    assert notif.is_read is False


async def test_list_for_user(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = NotificationRepository(session)
    await repo.create(
        user_id=user.id,
        type="like",
        title="N1",
        body="B1",
    )
    await repo.create(
        user_id=user.id,
        type="follow",
        title="N2",
        body="B2",
    )

    notifs = await repo.list_for_user(user.id)
    assert len(notifs) == 2


async def test_mark_read(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = NotificationRepository(session)
    notif = await repo.create(
        user_id=user.id,
        type="like",
        title="N",
        body="B",
    )
    assert await repo.unread_count(user.id) == 1

    await repo.mark_read(notif.id, user.id)
    assert await repo.unread_count(user.id) == 0


async def test_mark_all_read(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = NotificationRepository(session)
    await repo.create(
        user_id=user.id,
        type="a",
        title="N1",
        body="B1",
    )
    await repo.create(
        user_id=user.id,
        type="b",
        title="N2",
        body="B2",
    )
    assert await repo.unread_count(user.id) == 2

    await repo.mark_all_read(user.id)
    assert await repo.unread_count(user.id) == 0


async def test_mark_unread(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = NotificationRepository(session)
    notif = await repo.create(
        user_id=user.id,
        type="like",
        title="N",
        body="B",
    )
    await repo.mark_read(notif.id, user.id)
    assert await repo.unread_count(user.id) == 0
    await repo.mark_unread(notif.id, user.id)
    assert await repo.unread_count(user.id) == 1


async def test_delete(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = NotificationRepository(session)
    notif = await repo.create(
        user_id=user.id,
        type="like",
        title="N",
        body="B",
    )
    ok = await repo.delete(notif.id, user.id)
    assert ok
    notifs = await repo.list_for_user(user.id)
    assert len(notifs) == 0
    ok2 = await repo.delete(999, user.id)
    assert not ok2
