from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ws_manager import ws_manager
from app.repositories.notification import (
    NotificationRepository,
)

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


class NotificationService:
    def __init__(
        self, session: AsyncSession
    ) -> None:
        self._repo = NotificationRepository(session)

    async def create(
        self,
        user_id: int,
        ntype: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        n = await self._repo.create(
            user_id=user_id,
            type=ntype,
            title=title,
            body=body,
            data=data,
        )
        event = {
            "event": "notification",
            "id": n.id,
            "type": ntype,
            "title": title,
            "body": body,
            "data": data,
            "created_at": n.created_at.isoformat(),
        }
        await ws_manager.send_to_user(
            user_id, event
        )
        logger.info(
            "notification_created",
            notif_id=n.id,
            user_id=user_id,
            type=ntype,
        )
        return event

    async def list_notifications(
        self,
        user_id: int,
        cursor: int | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        items = await self._repo.list_for_user(
            user_id, cursor, limit
        )
        return [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "data": n.data,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in items
        ]

    async def unread_count(
        self, user_id: int
    ) -> int:
        return await self._repo.unread_count(
            user_id
        )

    async def mark_read(
        self, notification_id: int, user_id: int
    ) -> None:
        await self._repo.mark_read(
            notification_id, user_id
        )

    async def mark_all_read(
        self, user_id: int
    ) -> None:
        await self._repo.mark_all_read(user_id)
