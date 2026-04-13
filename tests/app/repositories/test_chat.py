import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.chat import ChatRepository

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


async def test_create_conversation(
    session: AsyncSession,
) -> None:
    u1, u2 = await _make_users(session)
    repo = ChatRepository(session)

    conv = await repo.create_conversation(
        type="dm", created_by_id=u1.id
    )

    assert conv.id is not None
    assert conv.type == "dm"


async def test_add_member_and_get_member_ids(
    session: AsyncSession,
) -> None:
    u1, u2 = await _make_users(session)
    repo = ChatRepository(session)
    conv = await repo.create_conversation(
        type="dm", created_by_id=u1.id
    )
    await repo.add_member(
        conversation_id=conv.id, user_id=u1.id
    )
    await repo.add_member(
        conversation_id=conv.id, user_id=u2.id
    )

    ids = await repo.get_member_ids(conv.id)
    assert set(ids) == {u1.id, u2.id}


async def test_get_member(
    session: AsyncSession,
) -> None:
    u1, u2 = await _make_users(session)
    repo = ChatRepository(session)
    conv = await repo.create_conversation(
        type="dm", created_by_id=u1.id
    )
    await repo.add_member(
        conversation_id=conv.id, user_id=u1.id
    )

    member = await repo.get_member(
        conv.id, u1.id
    )
    assert member is not None

    missing = await repo.get_member(
        conv.id, u2.id
    )
    assert missing is None


async def test_list_user_conversations(
    session: AsyncSession,
) -> None:
    u1, u2 = await _make_users(session)
    repo = ChatRepository(session)
    conv = await repo.create_conversation(
        type="dm", created_by_id=u1.id
    )
    await repo.add_member(
        conversation_id=conv.id, user_id=u1.id
    )

    convs = await repo.list_user_conversations(
        u1.id
    )
    assert len(convs) == 1
    assert (
        convs[0]["conversation"].id == conv.id
    )
