from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.login_history import LoginHistory


class LoginHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(
        self, user_id: int, *, limit: int = 50
    ) -> list[LoginHistory]:
        result = await self._session.execute(
            select(LoginHistory)
            .where(LoginHistory.user_id == user_id)
            .order_by(desc(LoginHistory.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())
