import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class TrackService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = TrackRepository(session)
        self._user_repo = UserRepository(session)

    async def _resolve_user(self, user_id: int) -> User:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)
        
        if not user:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

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
            track_id=track_id,
            user_id=user_id,
            is_public=is_public,
        )

    async def delete_by_owner(
        self, track_id: int, user_id: int
    ) -> Track | None:
        return await self._repo.delete_by_owner(
            track_id=track_id, user_id=user_id
        )

    async def list_public_by_user(
        self,
        user_id: int,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Track], int]:
        user = await self._resolve_user(user_id)
        offset = (page - 1) * size
        return await self._repo.list_public_by_user(
            user_id=user.id, offset=offset, limit=size
        )

    async def get_genres(self) -> list[str]:
        return await self._repo.get_unique_genres()
