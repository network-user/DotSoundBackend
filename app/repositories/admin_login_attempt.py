from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_login_attempt import (
    AdminLoginAttempt,
)


class AdminLoginAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        user_id: int | None,
        ip: str | None,
        ua: str | None,
        success: bool,
        reason: str | None = None,
    ) -> AdminLoginAttempt:
        row = AdminLoginAttempt(
            user_id=user_id,
            ip=ip,
            ua=ua,
            success=success,
            reason=reason,
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def count_failures_in_window(
        self,
        *,
        user_id: int,
        window_seconds: int,
    ) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
        result = await self._session.execute(
            select(func.count(AdminLoginAttempt.id)).where(
                AdminLoginAttempt.user_id == user_id,
                AdminLoginAttempt.success.is_(False),
                AdminLoginAttempt.created_at >= cutoff,
            )
        )
        return int(result.scalar_one())

    async def list_for_user(
        self, user_id: int, *, limit: int = 50
    ) -> list[AdminLoginAttempt]:
        result = await self._session.execute(
            select(AdminLoginAttempt)
            .where(AdminLoginAttempt.user_id == user_id)
            .order_by(desc(AdminLoginAttempt.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_recent(
        self,
        *,
        failed_only: bool = False,
        since: datetime | None = None,
        limit: int = 200,
    ) -> list[AdminLoginAttempt]:
        query = select(AdminLoginAttempt)
        if failed_only:
            query = query.where(AdminLoginAttempt.success.is_(False))
        if since is not None:
            query = query.where(AdminLoginAttempt.created_at >= since)
        query = query.order_by(desc(AdminLoginAttempt.created_at)).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())
