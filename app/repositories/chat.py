from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import (
    Conversation,
    ConversationMember,
)
from app.models.message import Message

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


class ChatRepository:
    def __init__(
        self, session: AsyncSession
    ) -> None:
        self._s = session

    async def create_conversation(
        self, **kwargs: Any
    ) -> Conversation:
        conv = Conversation(**kwargs)
        self._s.add(conv)
        await self._s.flush()
        await self._s.refresh(conv)
        return conv

    async def add_member(
        self, **kwargs: Any
    ) -> ConversationMember:
        m = ConversationMember(**kwargs)
        self._s.add(m)
        await self._s.flush()
        return m

    async def get_conversation(
        self, conv_id: int
    ) -> Conversation | None:
        return await self._s.get(
            Conversation, conv_id
        )

    async def get_member(
        self, conv_id: int, user_id: int
    ) -> ConversationMember | None:
        return await self._s.get(
            ConversationMember,
            (conv_id, user_id),
        )

    async def get_member_ids(
        self, conv_id: int
    ) -> list[int]:
        rows = await self._s.execute(
            select(
                ConversationMember.user_id
            ).where(
                ConversationMember.conversation_id
                == conv_id
            )
        )
        return list(rows.scalars().all())

    async def find_dm(
        self, user_a: int, user_b: int
    ) -> Conversation | None:
        sub = (
            select(
                ConversationMember.conversation_id
            )
            .where(
                ConversationMember.user_id.in_(
                    [user_a, user_b]
                )
            )
            .group_by(
                ConversationMember.conversation_id
            )
            .having(func.count() == 2)
            .subquery()
        )
        row = await self._s.execute(
            select(Conversation).where(
                Conversation.id.in_(
                    select(sub.c.conversation_id)
                ),
                Conversation.type == "dm",
            )
        )
        return row.scalar_one_or_none()

    async def list_user_conversations(
        self, user_id: int
    ) -> list[dict[str, Any]]:
        members_q = select(
            ConversationMember.conversation_id
        ).where(
            ConversationMember.user_id == user_id
        )

        last_msg = (
            select(
                Message.conversation_id,
                func.max(Message.created_at).label(
                    "last_at"
                ),
            )
            .where(Message.is_deleted.is_(False))
            .group_by(Message.conversation_id)
            .subquery()
        )

        rows = await self._s.execute(
            select(
                Conversation,
                ConversationMember,
                last_msg.c.last_at,
            )
            .join(
                ConversationMember,
                and_(
                    ConversationMember.conversation_id
                    == Conversation.id,
                    ConversationMember.user_id
                    == user_id,
                ),
            )
            .outerjoin(
                last_msg,
                last_msg.c.conversation_id
                == Conversation.id,
            )
            .where(
                Conversation.id.in_(members_q)
            )
            .order_by(
                ConversationMember.is_pinned.desc(),
                last_msg.c.last_at.desc().nullslast(),
            )
        )

        result: list[dict[str, Any]] = []
        for conv, member, last_at in rows:
            result.append(
                {
                    "conversation": conv,
                    "member": member,
                    "last_message_at": last_at,
                }
            )
        return result

    async def set_pinned(
        self,
        conv_id: int,
        user_id: int,
        pinned: bool,
    ) -> None:
        member = await self.get_member(
            conv_id, user_id
        )
        if member:
            member.is_pinned = pinned
            await self._s.flush()

    async def remove_member(
        self, conv_id: int, user_id: int
    ) -> None:
        await self._s.execute(
            delete(ConversationMember).where(
                ConversationMember.conversation_id
                == conv_id,
                ConversationMember.user_id
                == user_id,
            )
        )
        await self._s.flush()

    async def get_unread_count(
        self, conv_id: int, user_id: int
    ) -> int:
        member = await self.get_member(
            conv_id, user_id
        )
        if not member:
            return 0
        q = select(func.count(Message.id)).where(
            Message.conversation_id == conv_id,
            Message.is_deleted.is_(False),
        )
        if member.last_read_message_id:
            q = q.where(
                Message.id
                > member.last_read_message_id
            )
        result = await self._s.execute(q)
        return result.scalar_one()
