from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lyrics_job import LyricsJob


class LyricsJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_recent(
        self,
        *,
        statuses: Sequence[str],
        limit: int = 40,
    ) -> list[LyricsJob]:
        result = await self._session.execute(
            select(LyricsJob)
            .where(LyricsJob.status.in_(list(statuses)))
            .order_by(desc(LyricsJob.updated_at))
            .limit(limit)
        )
        return list(result.scalars().all())
