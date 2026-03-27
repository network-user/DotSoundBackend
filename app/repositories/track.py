import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.base import BaseRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class TrackRepository(BaseRepository[Track]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Track)

    async def list_active(
        self,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Track], int]:
        logger.debug(
            "db_list_tracks", offset=offset, limit=limit
        )
        total_result = await self._session.execute(
            select(func.count()).where(Track.is_active.is_(True))
        )
        total = total_result.scalar_one()

        tracks_result = await self._session.execute(
            select(Track)
            .where(Track.is_active.is_(True))
            .order_by(Track.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(tracks_result.scalars().all()), total

    async def search(
        self,
        query: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Track], int]:
        pattern = f"%{query}%"
        condition = (
            Track.is_active.is_(True)
            & (
                Track.title.ilike(pattern)
                | Track.artist.ilike(pattern)
            )
        )
        logger.debug(
            "db_search_tracks", query=query, offset=offset
        )
        total_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        total = total_result.scalar_one()

        tracks_result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.play_count.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(tracks_result.scalars().all()), total
