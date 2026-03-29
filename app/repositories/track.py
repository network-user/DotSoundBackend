import structlog
from sqlalchemy import func, select, update
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
        logger.debug("db_list_tracks", offset=offset, limit=limit)
        condition = Track.is_active.is_(True) & Track.is_public.is_(True)
        total_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        total = total_result.scalar_one()

        tracks_result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(tracks_result.scalars().all()), total

    async def list_by_user(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Track], int]:
        condition = (
            Track.is_active.is_(True) & (Track.uploaded_by_id == user_id)
        )
        total_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        total = total_result.scalar_one()

        tracks_result = await self._session.execute(
            select(Track)
            .where(condition)
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
            & Track.is_public.is_(True)
            & (
                Track.title.ilike(pattern)
                | Track.artist.ilike(pattern)
            )
        )
        logger.debug("db_search_tracks", query=query, offset=offset)
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

    async def increment_play_count(self, track_id: int) -> bool:
        result = await self._session.execute(
            update(Track)
            .where(
                Track.id == track_id,
                Track.is_active.is_(True),
            )
            .values(play_count=Track.play_count + 1)
        )
        updated = result.rowcount > 0
        if updated:
            logger.debug("db_play_count_incremented", track_id=track_id)
        else:
            logger.warning(
                "db_play_count_track_missing", track_id=track_id
            )
        return updated

    async def update_visibility(
        self, track_id: int, user_id: int, is_public: bool
    ) -> Track | None:
        result = await self._session.execute(
            update(Track)
            .where(
                Track.id == track_id,
                Track.uploaded_by_id == user_id,
                Track.is_active.is_(True),
            )
            .values(is_public=is_public)
            .returning(Track)
        )
        await self._session.commit()
        return result.scalar_one_or_none()

    async def delete_by_owner(
        self, track_id: int, user_id: int
    ) -> Track | None:
        track = await self.get_by_id(track_id)
        if not track or track.uploaded_by_id != user_id:
            return None
        track.is_active = False
        await self._session.commit()
        return track
