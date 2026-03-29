import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class TrackService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = TrackRepository(session)

    async def list_tracks(
        self,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Track], int]:
        offset = (page - 1) * size
        tracks, total = await self._repo.list_active(
            offset=offset, limit=size
        )
        logger.info(
            "tracks_listed",
            page=page,
            size=size,
            total=total,
            returned=len(tracks),
        )
        return tracks, total

    async def get_track(self, track_id: int) -> Track | None:
        track = await self._repo.get_by_id(track_id)
        if not track or not track.is_active:
            logger.warning("track_not_found", track_id=track_id)
            return None
        logger.debug("track_fetched", track_id=track_id)
        return track

    async def search(
        self,
        query: str,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Track], int]:
        offset = (page - 1) * size
        tracks, total = await self._repo.search(
            query=query, offset=offset, limit=size
        )
        logger.info(
            "tracks_searched",
            query=query,
            page=page,
            total=total,
        )
        return tracks, total

    async def list_by_user(
        self,
        user_id: int,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[Track], int]:
        offset = (page - 1) * size
        return await self._repo.list_by_user(
            user_id=user_id, offset=offset, limit=size
        )

    async def update_visibility(
        self, track_id: int, user_id: int, is_public: bool
    ) -> Track | None:
        return await self._repo.update_visibility(
            track_id=track_id, user_id=user_id, is_public=is_public
        )

    async def delete_by_owner(
        self, track_id: int, user_id: int
    ) -> Track | None:
        return await self._repo.delete_by_owner(
            track_id=track_id, user_id=user_id
        )
