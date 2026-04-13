import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.chat import ChatRepository
from app.repositories.message import (
    MessageRepository,
)

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
    chat_repo = ChatRepository(session)
    conv = await chat_repo.create_conversation(
        type="dm", created_by_id=user.id
    )
    await chat_repo.add_member(
        conversation_id=conv.id, user_id=user.id
    )
    return user, conv


async def test_create_message(
    session: AsyncSession,
) -> None:
    user, conv = await _seed(session)
    repo = MessageRepository(session)

    msg = await repo.create(
        conversation_id=conv.id,
        sender_id=user.id,
        type="text",
    )
    assert msg.id is not None
    assert msg.conversation_id == conv.id


async def test_list_messages(
    session: AsyncSession,
) -> None:
    user, conv = await _seed(session)
    repo = MessageRepository(session)
    await repo.create(
        conversation_id=conv.id,
        sender_id=user.id,
        type="text",
    )
    await repo.create(
        conversation_id=conv.id,
        sender_id=user.id,
        type="text",
    )

    messages = await repo.list_messages(conv.id)
    assert len(messages) == 2


async def test_soft_delete(
    session: AsyncSession,
) -> None:
    user, conv = await _seed(session)
    repo = MessageRepository(session)
    msg = await repo.create(
        conversation_id=conv.id,
        sender_id=user.id,
        type="text",
    )

    await repo.soft_delete(msg.id)
    await session.refresh(msg)
    assert msg.is_deleted is True

    visible = await repo.list_messages(conv.id)
    assert len(visible) == 0
