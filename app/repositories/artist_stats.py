from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist_follow import ArtistFollow
from app.models.artist_monthly_stats import ArtistMonthlyStats
from app.models.like import Like
from app.models.listen_event import ListenEvent
from app.models.artist import TrackArtist


def _month_bounds(
    year: int, month: int
) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=UTC)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(year, month + 1, 1, tzinfo=UTC)
    return start, end


class ArtistStatsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_active_listeners(
        self,
        artist_id: int,
        year: int,
        month: int,
    ) -> int:
        start, end = _month_bounds(year, month)
        result = await self._session.execute(
            select(
                func.count(
                    func.distinct(ListenEvent.user_id)
                )
            )
            .join(
                TrackArtist,
                TrackArtist.track_id
                == ListenEvent.track_id,
            )
            .where(
                TrackArtist.artist_id == artist_id,
                ListenEvent.started_at >= start,
                ListenEvent.started_at < end,
            )
        )
        return result.scalar_one() or 0

    async def count_total_plays(
        self,
        artist_id: int,
        year: int,
        month: int,
    ) -> int:
        start, end = _month_bounds(year, month)
        result = await self._session.execute(
            select(func.count(ListenEvent.id))
            .join(
                TrackArtist,
                TrackArtist.track_id == ListenEvent.track_id,
            )
            .where(
                TrackArtist.artist_id == artist_id,
                ListenEvent.started_at >= start,
                ListenEvent.started_at < end,
            )
        )
        return result.scalar_one() or 0

    async def count_total_likes(
        self,
        artist_id: int,
        year: int,
        month: int,
    ) -> int:
        start, end = _month_bounds(year, month)
        result = await self._session.execute(
            select(func.count(Like.track_id))
            .join(
                TrackArtist,
                TrackArtist.track_id == Like.track_id,
            )
            .where(
                TrackArtist.artist_id == artist_id,
                Like.created_at >= start,
                Like.created_at < end,
            )
        )
        return result.scalar_one() or 0

    async def count_total_followers(
        self, artist_id: int
    ) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(ArtistFollow)
            .where(ArtistFollow.artist_id == artist_id)
        )
        return result.scalar_one() or 0

    async def upsert_snapshot(
        self,
        artist_id: int,
        year: int,
        month: int,
        unique_listeners: int,
        total_plays: int = 0,
        total_likes: int = 0,
        total_followers: int = 0,
    ) -> None:
        now = datetime.now(UTC)
        existing = await self._session.execute(
            select(ArtistMonthlyStats).where(
                ArtistMonthlyStats.artist_id == artist_id,
                ArtistMonthlyStats.year == year,
                ArtistMonthlyStats.month == month,
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            await self._session.execute(
                update(ArtistMonthlyStats)
                .where(
                    ArtistMonthlyStats.artist_id
                    == artist_id,
                    ArtistMonthlyStats.year == year,
                    ArtistMonthlyStats.month == month,
                )
                .values(
                    unique_listeners=unique_listeners,
                    total_plays=total_plays,
                    total_likes=total_likes,
                    total_followers=total_followers,
                    snapshotted_at=now,
                )
            )
        else:
            self._session.add(
                ArtistMonthlyStats(
                    artist_id=artist_id,
                    year=year,
                    month=month,
                    unique_listeners=unique_listeners,
                    total_plays=total_plays,
                    total_likes=total_likes,
                    total_followers=total_followers,
                    snapshotted_at=now,
                )
            )
            await self._session.flush()

    async def get_history(
        self,
        artist_id: int,
        limit: int = 24,
    ) -> list[ArtistMonthlyStats]:
        result = await self._session.execute(
            select(ArtistMonthlyStats)
            .where(
                ArtistMonthlyStats.artist_id == artist_id
            )
            .order_by(
                ArtistMonthlyStats.year.desc(),
                ArtistMonthlyStats.month.desc(),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def has_snapshot(
        self, artist_id: int, year: int, month: int
    ) -> bool:
        result = await self._session.execute(
            select(ArtistMonthlyStats.id).where(
                ArtistMonthlyStats.artist_id == artist_id,
                ArtistMonthlyStats.year == year,
                ArtistMonthlyStats.month == month,
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_all_artist_ids(self) -> list[int]:
        from app.models.artist import Artist

        result = await self._session.execute(
            select(Artist.id)
        )
        return list(result.scalars().all())
