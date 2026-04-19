from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_action_log import AdminActionLog


class AdminActionLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write(
        self,
        *,
        user_id: int,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        ip: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> AdminActionLog:
        row = AdminActionLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip=ip,
            meta=meta,
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_paginated(
        self,
        *,
        user_id: int | None = None,
        action: str | None = None,
        target_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[AdminActionLog], int]:
        query = select(AdminActionLog)
        count_query = select(func.count(AdminActionLog.id))

        if user_id is not None:
            query = query.where(AdminActionLog.user_id == user_id)
            count_query = count_query.where(AdminActionLog.user_id == user_id)
        if action is not None:
            query = query.where(AdminActionLog.action == action)
            count_query = count_query.where(AdminActionLog.action == action)
        if target_type is not None:
            query = query.where(AdminActionLog.target_type == target_type)
            count_query = count_query.where(
                AdminActionLog.target_type == target_type
            )
        if since is not None:
            query = query.where(AdminActionLog.created_at >= since)
            count_query = count_query.where(AdminActionLog.created_at >= since)
        if until is not None:
            query = query.where(AdminActionLog.created_at <= until)
            count_query = count_query.where(AdminActionLog.created_at <= until)

        offset = (page - 1) * size
        query = (
            query.order_by(desc(AdminActionLog.created_at))
            .offset(offset)
            .limit(size)
        )

        result = await self._session.execute(query)
        rows = list(result.scalars().all())
        count_result = await self._session.execute(count_query)
        total = int(count_result.scalar_one())
        return rows, total

    async def stream_for_export(
        self,
        *,
        user_id: int | None = None,
        action: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[AdminActionLog]:
        query = select(AdminActionLog)
        if user_id is not None:
            query = query.where(AdminActionLog.user_id == user_id)
        if action is not None:
            query = query.where(AdminActionLog.action == action)
        if since is not None:
            query = query.where(AdminActionLog.created_at >= since)
        if until is not None:
            query = query.where(AdminActionLog.created_at <= until)
        query = query.order_by(desc(AdminActionLog.created_at)).limit(50_000)
        result = await self._session.execute(query)
        return list(result.scalars().all())
