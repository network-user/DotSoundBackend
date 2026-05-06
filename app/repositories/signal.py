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
        last_position: int | None = None,
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
            last_position_seconds=(
                last_position if last_position is not None else 0
            ),
        )

    async def latest_resume_position(
        self,
        user_id: int,
        track_ids: list[int],
    ) -> dict[int, int]:
        """Return last-recorded position (sec) per track, only for
        events the user did not finish (so we don't suggest resuming
        the very last second of a completed listen).
        """
        if not track_ids:
            return {}
        from sqlalchemy import and_, func

        stmt = (
            select(
                ListenEvent.track_id,
                func.max(ListenEvent.created_at),
            )
            .where(
                and_(
                    ListenEvent.user_id == user_id,
                    ListenEvent.track_id.in_(track_ids),
                    ListenEvent.completed.is_(False),
                    ListenEvent.skipped.is_(False),
                    ListenEvent.last_position_seconds > 0,
                )
            )
            .group_by(ListenEvent.track_id)
        )
        latest_keys = (
            await self._session.execute(stmt)
        ).all()
        if not latest_keys:
            return {}
        out: dict[int, int] = {}
        for track_id, latest_ts in latest_keys:
            row = (
                await self._session.execute(
                    select(
                        ListenEvent.last_position_seconds
                    )
                    .where(
                        ListenEvent.user_id == user_id,
                        ListenEvent.track_id == track_id,
                        ListenEvent.created_at == latest_ts,
                    )
                    .limit(1)
                )
            ).first()
            if row and row[0] is not None:
                out[int(track_id)] = int(row[0])
        return out

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

    async def count_by_track_since(
        self, track_id: int, since: datetime
    ) -> int:
        from sqlalchemy import func

        r = await self._session.execute(
            select(func.count())
            .where(
                ListenEvent.track_id == track_id,
                ListenEvent.created_at >= since,
            )
        )
        return int(r.scalar_one())

    async def get_user_listen_rows_since(
        self,
        user_id: int,
        since: datetime | None,
    ) -> list[tuple[int, int, int | None]]:
        """Return raw ``(track_id, duration_listened, total_duration)``
        rows for personal-stats aggregation. Period filter ``since``
        is exclusive of older events.
        """
        stmt = select(
            ListenEvent.track_id,
            ListenEvent.duration_listened_seconds,
            ListenEvent.total_duration_seconds,
        ).where(ListenEvent.user_id == user_id)
        if since is not None:
            stmt = stmt.where(
                ListenEvent.created_at >= since
            )
        rows = (
            await self._session.execute(stmt)
        ).all()
        return [
            (int(r[0]), int(r[1] or 0), r[2])
            for r in rows
        ]


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
