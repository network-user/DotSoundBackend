from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listen_event import ListenEvent
from app.models.search_event import SearchEvent
from app.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class ListenEventRepository(
    BaseRepository[ListenEvent]
):
    def __init__(
        self, session: AsyncSession
    ) -> None:
        super().__init__(session, ListenEvent)

    async def create_event(
        self,
        user_id: int,
        track_id: int,
        started_at: datetime,
        duration_listened: int,
        total_duration: int | None,
        completed: bool,
        skipped: bool,
        source_context: str | None,
    ) -> ListenEvent:
        return await self.create(
            user_id=user_id,
            track_id=track_id,
            started_at=started_at,
            duration_listened_seconds=(
                duration_listened
            ),
            total_duration_seconds=total_duration,
            completed=completed,
            skipped=skipped,
            source_context=source_context,
        )

    async def get_recent(
        self,
        user_id: int,
        limit: int = 100,
    ) -> list[ListenEvent]:
        result = await self._session.execute(
            select(ListenEvent)
            .where(
                ListenEvent.user_id == user_id
            )
            .order_by(
                ListenEvent.created_at.desc()
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_for_user(
        self, user_id: int
    ) -> int:
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count()).where(
                ListenEvent.user_id == user_id
            )
        )
        return result.scalar_one()


class SearchEventRepository(
    BaseRepository[SearchEvent]
):
    def __init__(
        self, session: AsyncSession
    ) -> None:
        super().__init__(session, SearchEvent)

    async def create_event(
        self,
        user_id: int,
        query: str,
        results_count: int,
        clicked_track_id: int | None,
    ) -> SearchEvent:
        return await self.create(
            user_id=user_id,
            query=query,
            results_count=results_count,
            clicked_track_id=clicked_track_id,
        )
