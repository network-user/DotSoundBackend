from __future__ import annotations

from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ws_manager import ws_manager
from app.models.message import Message
from app.repositories.block import BlockRepository
from app.repositories.chat import ChatRepository
from app.repositories.message import (
    MessageRepository,
)
from app.services.encryption_service import (
    decrypt_message,
    encrypt_message,
)

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


class MessageService:
    def __init__(
        self, session: AsyncSession
    ) -> None:
        self._msg_repo = MessageRepository(session)
        self._chat_repo = ChatRepository(session)
        self._block_repo = BlockRepository(session)
        self._session = session

    async def send_message(
        self,
        conversation_id: int,
        sender_id: int,
        content: str,
        msg_type: str = "text",
        reply_to_id: int | None = None,
        shared_track_id: int | None = None,
        broadcast: bool = True,
    ) -> dict[str, Any]:
        member = await self._chat_repo.get_member(
            conversation_id, sender_id
        )
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member",
            )

        members = (
            await self._chat_repo.get_member_ids(
                conversation_id
            )
        )
        for mid in members:
            if mid == sender_id:
                continue
            if await self._block_repo.is_blocked(
                sender_id, mid
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Blocked",
                )

        encrypted, nonce = await encrypt_message(
            self._session,
            conversation_id,
            content,
        )

        msg = await self._msg_repo.create(
            conversation_id=conversation_id,
            sender_id=sender_id,
            type=msg_type,
            encrypted_content=encrypted,
            content_nonce=nonce,
            reply_to_id=reply_to_id,
            shared_track_id=shared_track_id,
        )

        result = {
            "id": msg.id,
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "type": msg_type,
            "content": content,
            "reply_to_id": reply_to_id,
            "shared_track_id": shared_track_id,
            "created_at": msg.created_at.isoformat(),
            "attachments": [],
            "reactions": [],
        }
        if broadcast:
            await ws_manager.send_to_conversation(
                members,
                {
                    "event": "message.new",
                    "message_id": msg.id,
                    **result,
                },
            )

        logger.info(
            "message_sent",
            msg_id=msg.id,
            conv_id=conversation_id,
        )
        return result

    async def delete_message(
        self, message_id: int, user_id: int
    ) -> None:
        msg = await self._msg_repo.get_by_id(
            message_id
        )
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )
        member = await self._chat_repo.get_member(
            msg.conversation_id, user_id
        )
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member",
            )

        await self._msg_repo.soft_delete(message_id)

        members = (
            await self._chat_repo.get_member_ids(
                msg.conversation_id
            )
        )
        await ws_manager.send_to_conversation(
            members,
            {
                "event": "message.deleted",
                "message_id": message_id,
                "conversation_id": msg.conversation_id,
            },
        )

    async def get_messages(
        self,
        conversation_id: int,
        user_id: int,
        cursor: int | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        member = await self._chat_repo.get_member(
            conversation_id, user_id
        )
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member",
            )

        msgs = await self._msg_repo.list_messages(
            conversation_id, cursor, limit
        )

        return [
            await self._serialize_message(
                msg, conversation_id
            )
            for msg in msgs
        ]

    async def add_reaction(
        self,
        message_id: int,
        user_id: int,
        reaction_type: str,
    ) -> None:
        msg = await self._msg_repo.get_by_id(
            message_id
        )
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )
        member = await self._chat_repo.get_member(
            msg.conversation_id, user_id
        )
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member",
            )
        await self._msg_repo.add_reaction(
            message_id, user_id, reaction_type
        )
        members = (
            await self._chat_repo.get_member_ids(
                msg.conversation_id
            )
        )
        await ws_manager.send_to_conversation(
            members,
            {
                "event": "message.reaction",
                "message_id": message_id,
                "conversation_id": msg.conversation_id,
                "user_id": user_id,
                "reaction_type": reaction_type,
                "action": "add",
            },
        )

    async def remove_reaction(
        self,
        message_id: int,
        user_id: int,
        reaction_type: str,
    ) -> None:
        msg = await self._msg_repo.get_by_id(
            message_id
        )
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )
        member = await self._chat_repo.get_member(
            msg.conversation_id, user_id
        )
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member",
            )
        await self._msg_repo.remove_reaction(
            message_id, user_id, reaction_type
        )
        members = (
            await self._chat_repo.get_member_ids(
                msg.conversation_id
            )
        )
        await ws_manager.send_to_conversation(
            members,
            {
                "event": "message.reaction",
                "message_id": message_id,
                "conversation_id": msg.conversation_id,
                "user_id": user_id,
                "reaction_type": reaction_type,
                "action": "remove",
            },
        )

    async def mark_as_read(
        self,
        conversation_id: int,
        user_id: int,
        message_id: int,
    ) -> None:
        member = await self._chat_repo.get_member(
            conversation_id, user_id
        )
        if not member:
            return
        member.last_read_message_id = message_id
        await self._session.flush()

        members = (
            await self._chat_repo.get_member_ids(
                conversation_id
            )
        )
        await ws_manager.send_to_conversation(
            members,
            {
                "event": "read_receipt",
                "conversation_id": conversation_id,
                "user_id": user_id,
                "message_id": message_id,
            },
        )

    async def broadcast_message(
        self, message_id: int
    ) -> None:
        msg = await self._msg_repo.get_by_id(
            message_id
        )
        if not msg or msg.is_deleted:
            return
        members = (
            await self._chat_repo.get_member_ids(
                msg.conversation_id
            )
        )
        payload = await self._serialize_message(
            msg, msg.conversation_id
        )
        await ws_manager.send_to_conversation(
            members,
            {
                "event": "message.new",
                "message_id": msg.id,
                **payload,
            },
        )

    async def _serialize_message(
        self,
        msg: Message,
        conversation_id: int,
    ) -> dict[str, Any]:
        text = ""
        if (
            msg.encrypted_content
            and msg.content_nonce
        ):
            text = await decrypt_message(
                self._session,
                conversation_id,
                msg.encrypted_content,
                msg.content_nonce,
            )

        attachments = await self._msg_repo.get_attachments(
            msg.id
        )
        reactions = await self._msg_repo.get_reactions(
            msg.id
        )
        return {
            "id": msg.id,
            "conversation_id": conversation_id,
            "sender_id": msg.sender_id,
            "type": msg.type,
            "content": text,
            "reply_to_id": msg.reply_to_id,
            "shared_track_id": msg.shared_track_id,
            "created_at": msg.created_at.isoformat(),
            "attachments": [
                {
                    "id": a.id,
                    "file_key": a.file_key,
                    "file_type": a.file_type,
                    "file_size_bytes": a.file_size_bytes,
                    "duration_seconds": a.duration_seconds,
                    "waveform": a.waveform,
                    "width": a.width,
                    "height": a.height,
                }
                for a in attachments
            ],
            "reactions": [
                {
                    "user_id": r.user_id,
                    "reaction_type": r.reaction_type,
                }
                for r in reactions
            ],
        }
