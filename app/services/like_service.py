import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.like import LikeRepository
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class LikeService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = LikeRepository(session)
        self._track_repo = TrackRepository(session)

    async def toggle(
        self, user_id: int, track_id: int
    ) -> bool:
        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )

        existing = await self._repo.get(user_id, track_id)
        if existing:
            await self._repo.remove(user_id, track_id)
            liked = False
        else:
            await self._repo.add(user_id, track_id)
            liked = True

        logger.info(
            "like_toggled",
            user_id=user_id,
            track_id=track_id,
            liked=liked,
        )
        return liked

    async def list_liked(
        self,
        user_id: int,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Track], int]:
        offset = (page - 1) * size
        tracks, total = await self._repo.list_liked_tracks(
            user_id=user_id, offset=offset, limit=size
        )
        logger.info(
            "liked_tracks_listed",
            user_id=user_id,
            total=total,
        )
        return tracks, total

    async def is_liked(
        self, user_id: int, track_id: int
    ) -> bool:
        like = await self._repo.get(user_id, track_id)
        return like is not None
