from datetime import datetime, timedelta

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.like import Like
from app.models.listen_event import ListenEvent
from app.models.search_event import SearchEvent
from app.models.track import Track
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

    async def aggregate_user_top_tracks(
        self,
        user_id: int,
        *,
        since: datetime | None,
        candidate_limit: int = 200,
    ) -> list[tuple[int, int, int]]:
        """Return ``(track_id, completed_listens, likes)`` rows.

        ``completed_listens`` counts events with ``completed=True``;
        ``likes`` is 1 if the user has liked the track else 0
        (per the policy contract — we do not need richer
        like-history granularity here).
        """
        completed_count = func.sum(
            case((ListenEvent.completed.is_(True), 1), else_=0)
        )
        liked_flag = func.max(
            case((Like.user_id.is_not(None), 1), else_=0)
        )
        stmt = (
            select(
                ListenEvent.track_id,
                completed_count.label("completed"),
                liked_flag.label("liked"),
            )
            .outerjoin(
                Like,
                (Like.track_id == ListenEvent.track_id)
                & (Like.user_id == user_id),
            )
            .where(ListenEvent.user_id == user_id)
            .group_by(ListenEvent.track_id)
            .order_by(completed_count.desc())
            .limit(candidate_limit)
        )
        if since is not None:
            stmt = stmt.where(
                ListenEvent.created_at >= since
            )
        rows = (await self._session.execute(stmt)).all()
        return [
            (int(r[0]), int(r[1] or 0), int(r[2] or 0))
            for r in rows
        ]

    async def aggregate_user_top_genres(
        self,
        user_id: int,
        *,
        since: datetime | None,
        candidate_limit: int = 50,
    ) -> list[tuple[str, int]]:
        completed_count = func.sum(
            case((ListenEvent.completed.is_(True), 1), else_=0)
        )
        stmt = (
            select(
                Track.genre,
                completed_count.label("completed"),
            )
            .join(Track, Track.id == ListenEvent.track_id)
            .where(
                ListenEvent.user_id == user_id,
                Track.genre.is_not(None),
                Track.genre != "",
            )
            .group_by(Track.genre)
            .order_by(completed_count.desc())
            .limit(candidate_limit)
        )
        if since is not None:
            stmt = stmt.where(
                ListenEvent.created_at >= since
            )
        rows = (await self._session.execute(stmt)).all()
        return [
            (str(r[0]), int(r[1] or 0)) for r in rows if r[0]
        ]

    @staticmethod
    def window_to_since(
        window: str, *, now: datetime | None = None
    ) -> datetime | None:
        """Map a normalized window code to a UTC ``since``."""
        from datetime import UTC

        moment = now if now is not None else datetime.now(UTC)
        if window == "7d":
            return moment - timedelta(days=7)
        if window == "30d":
            return moment - timedelta(days=30)
        if window == "90d":
            return moment - timedelta(days=90)
        return None

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
