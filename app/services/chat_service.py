from __future__ import annotations

from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import (
    Conversation,
    ConversationMember,
)
from app.repositories.block import BlockRepository
from app.repositories.chat import ChatRepository
from app.repositories.user import UserRepository

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


def _conv_to_dict(
    conv: Conversation,
) -> dict[str, Any]:
    return {
        "id": conv.id,
        "type": conv.type,
        "title": conv.title,
        "created_by_id": conv.created_by_id,
        "created_at": conv.created_at.isoformat()
        if conv.created_at
        else None,
    }


def _member_to_dict(
    m: ConversationMember,
) -> dict[str, Any]:
    return {
        "is_pinned": m.is_pinned,
        "is_muted": m.is_muted,
        "last_read_message_id": m.last_read_message_id,
    }


class ChatService:
    def __init__(
        self, session: AsyncSession
    ) -> None:
        self._session = session
        self._repo = ChatRepository(session)
        self._block_repo = BlockRepository(session)
        self._user_repo = UserRepository(session)

    async def create_dm(
        self, user_id: int, target_id: int
    ) -> dict[str, Any]:
        if user_id == target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot message yourself",
            )
        if await self._block_repo.is_blocked(
            user_id, target_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is blocked",
            )

        existing = await self._repo.find_dm(
            user_id, target_id
        )
        if existing:
            return {
                "conversation": _conv_to_dict(
                    existing
                )
            }

        conv = await self._repo.create_conversation(
            type="dm", created_by_id=user_id
        )
        await self._repo.add_member(
            conversation_id=conv.id,
            user_id=user_id,
            role="owner",
        )
        await self._repo.add_member(
            conversation_id=conv.id,
            user_id=target_id,
            role="member",
        )
        logger.info(
            "dm_created",
            conv_id=conv.id,
            user_a=user_id,
            user_b=target_id,
        )
        return {
            "conversation": _conv_to_dict(conv)
        }

    async def create_group(
        self,
        user_id: int,
        title: str,
        member_ids: list[int],
    ) -> dict[str, Any]:
        conv = await self._repo.create_conversation(
            type="group",
            title=title,
            created_by_id=user_id,
        )
        await self._repo.add_member(
            conversation_id=conv.id,
            user_id=user_id,
            role="owner",
        )
        for mid in member_ids:
            if mid == user_id:
                continue
            if await self._block_repo.is_blocked(
                user_id, mid
            ):
                continue
            await self._repo.add_member(
                conversation_id=conv.id,
                user_id=mid,
                role="member",
            )
        logger.info(
            "group_created",
            conv_id=conv.id,
            owner=user_id,
        )
        return {
            "conversation": _conv_to_dict(conv)
        }

    async def list_chats(
        self, user_id: int
    ) -> list[dict[str, Any]]:
        rows = (
            await self._repo.list_user_conversations(
                user_id
            )
        )
        dm_conv_ids = [
            r["conversation"].id
            for r in rows
            if r["conversation"].type == "dm"
        ]
        peers = await self._repo.get_dm_peers(
            user_id, dm_conv_ids
        )

        result: list[dict[str, Any]] = []
        for r in rows:
            item: dict[str, Any] = {
                "conversation": _conv_to_dict(
                    r["conversation"]
                ),
                "member": _member_to_dict(
                    r["member"]
                ),
                "last_message_at": (
                    r["last_message_at"].isoformat()
                    if r["last_message_at"]
                    else None
                ),
            }
            peer = peers.get(r["conversation"].id)
            if peer:
                item["peer"] = {
                    "id": peer.id,
                    "first_name": peer.first_name,
                    "last_name": peer.last_name,
                    "display_name": peer.display_name,
                    "username": peer.username,
                    "avatar_key": peer.avatar_key,
                }
            result.append(item)
        return result

    async def pin_chat(
        self, user_id: int, conv_id: int
    ) -> None:
        await self._ensure_member(
            conv_id, user_id
        )
        await self._repo.set_pinned(
            conv_id, user_id, True
        )

    async def unpin_chat(
        self, user_id: int, conv_id: int
    ) -> None:
        await self._ensure_member(
            conv_id, user_id
        )
        await self._repo.set_pinned(
            conv_id, user_id, False
        )

    async def add_member(
        self,
        user_id: int,
        conv_id: int,
        new_member_id: int,
    ) -> None:
        await self._ensure_not_saved(conv_id)
        member = await self._repo.get_member(
            conv_id, user_id
        )
        if not member or member.role not in (
            "owner",
            "admin",
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed",
            )
        await self._repo.add_member(
            conversation_id=conv_id,
            user_id=new_member_id,
            role="member",
        )

    async def remove_member(
        self,
        user_id: int,
        conv_id: int,
        target_id: int,
    ) -> None:
        await self._ensure_not_saved(conv_id)
        member = await self._repo.get_member(
            conv_id, user_id
        )
        if not member or member.role not in (
            "owner",
            "admin",
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed",
            )
        await self._repo.remove_member(
            conv_id, target_id
        )

    async def get_member_ids(
        self, conv_id: int
    ) -> list[int]:
        return await self._repo.get_member_ids(
            conv_id
        )

    async def get_or_create_saved(
        self, user_id: int
    ) -> dict[str, Any]:
        existing = await self._repo.find_saved(user_id)
        if existing:
            return {
                "conversation": _conv_to_dict(
                    existing
                )
            }

        try:
            conv = await self._repo.create_conversation(
                type="saved",
                title="Избранное",
                created_by_id=user_id,
            )
            await self._repo.add_member(
                conversation_id=conv.id,
                user_id=user_id,
                role="owner",
            )
        except IntegrityError:
            await self._session.rollback()
            existing = await self._repo.find_saved(
                user_id
            )
            if existing:
                return {
                    "conversation": _conv_to_dict(
                        existing
                    )
                }
            raise
        logger.info(
            "saved_created",
            conv_id=conv.id,
            user_id=user_id,
        )
        return {
            "conversation": _conv_to_dict(conv)
        }

    async def search_users(
        self, query: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        users = await self._user_repo.search(
            query, limit
        )
        return [
            {
                "id": u.id,
                "username": u.username,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "display_name": u.display_name,
                "avatar_key": u.avatar_key,
            }
            for u in users
        ]

    async def _ensure_member(
        self, conv_id: int, user_id: int
    ) -> None:
        m = await self._repo.get_member(
            conv_id, user_id
        )
        if not m:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member",
            )

    async def _ensure_not_saved(
        self, conv_id: int
    ) -> None:
        conv = await self._repo.get_conversation(
            conv_id
        )
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        if conv.type == "saved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Saved chat membership is immutable",
            )
