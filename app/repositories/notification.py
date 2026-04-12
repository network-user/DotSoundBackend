from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


class NotificationRepository:
    def __init__(
        self, session: AsyncSession
    ) -> None:
        self._s = session

    async def create(
        self, **kwargs: Any
    ) -> Notification:
        n = Notification(**kwargs)
        self._s.add(n)
        await self._s.flush()
        await self._s.refresh(n)
        return n

    async def list_for_user(
        self,
        user_id: int,
        cursor: int | None = None,
        limit: int = 20,
    ) -> list[Notification]:
        q = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.id.desc())
            .limit(limit)
        )
        if cursor:
            q = q.where(Notification.id < cursor)
        rows = await self._s.execute(q)
        return list(rows.scalars().all())

    async def unread_count(
        self, user_id: int
    ) -> int:
        result = await self._s.scalar(
            select(func.count()).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
        return result or 0

    async def mark_read(
        self, notification_id: int, user_id: int
    ) -> None:
        await self._s.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
            .values(is_read=True)
        )
        await self._s.flush()

    async def mark_all_read(
        self, user_id: int
    ) -> None:
        await self._s.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
        )
        await self._s.flush()
