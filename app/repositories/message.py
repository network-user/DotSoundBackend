from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import (
    Message,
    MessageAttachment,
    MessageReaction,
)

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


class MessageRepository:
    def __init__(
        self, session: AsyncSession
    ) -> None:
        self._s = session

    async def create(
        self, **kwargs: Any
    ) -> Message:
        msg = Message(**kwargs)
        self._s.add(msg)
        await self._s.flush()
        await self._s.refresh(msg)
        return msg

    async def get_by_id(
        self, msg_id: int
    ) -> Message | None:
        return await self._s.get(Message, msg_id)

    async def list_messages(
        self,
        conv_id: int,
        cursor: int | None = None,
        limit: int = 20,
    ) -> list[Message]:
        q = (
            select(Message)
            .where(
                Message.conversation_id == conv_id,
                Message.is_deleted.is_(False),
            )
            .order_by(Message.id.desc())
            .limit(limit)
        )
        if cursor:
            q = q.where(Message.id < cursor)
        rows = await self._s.execute(q)
        return list(rows.scalars().all())

    async def soft_delete(
        self, msg_id: int
    ) -> None:
        msg = await self.get_by_id(msg_id)
        if msg:
            msg.is_deleted = True
            await self._s.flush()

    async def add_attachment(
        self, **kwargs: Any
    ) -> MessageAttachment:
        att = MessageAttachment(**kwargs)
        self._s.add(att)
        await self._s.flush()
        await self._s.refresh(att)
        return att

    async def get_attachments(
        self, msg_id: int
    ) -> list[MessageAttachment]:
        rows = await self._s.execute(
            select(MessageAttachment).where(
                MessageAttachment.message_id
                == msg_id
            )
        )
        return list(rows.scalars().all())

    async def add_reaction(
        self,
        msg_id: int,
        user_id: int,
        reaction_type: str,
    ) -> MessageReaction:
        r = MessageReaction(
            message_id=msg_id,
            user_id=user_id,
            reaction_type=reaction_type,
        )
        self._s.add(r)
        await self._s.flush()
        return r

    async def remove_reaction(
        self,
        msg_id: int,
        user_id: int,
        reaction_type: str,
    ) -> None:
        await self._s.execute(
            delete(MessageReaction).where(
                and_(
                    MessageReaction.message_id
                    == msg_id,
                    MessageReaction.user_id
                    == user_id,
                    MessageReaction.reaction_type
                    == reaction_type,
                )
            )
        )
        await self._s.flush()

    async def get_reactions(
        self, msg_id: int
    ) -> list[MessageReaction]:
        rows = await self._s.execute(
            select(MessageReaction).where(
                MessageReaction.message_id == msg_id
            )
        )
        return list(rows.scalars().all())

    async def get_last_message(
        self, conv_id: int
    ) -> Message | None:
        row = await self._s.execute(
            select(Message)
            .where(
                Message.conversation_id == conv_id,
                Message.is_deleted.is_(False),
            )
            .order_by(Message.id.desc())
            .limit(1)
        )
        return row.scalar_one_or_none()
