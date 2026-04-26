import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.dislike import DislikeRepository
from app.repositories.like import LikeRepository
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class LikeService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = LikeRepository(session)
        self._track_repo = TrackRepository(session)
        self._user_repo = UserRepository(session)
        self._dislike_repo = DislikeRepository(session)

    async def toggle(
        self, user_id: int, track_id: int
    ) -> bool:
        # Resolve user_id: could be internal ID or Telegram ID
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        resolved_user_id = user.id

        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )

        existing = await self._repo.get(resolved_user_id, track_id)
        if existing:
            await self._repo.remove(resolved_user_id, track_id)
            liked = False
        else:
            # When liking, remove dislike if it exists
            await self._dislike_repo.remove(resolved_user_id, track_id)
            await self._repo.add(resolved_user_id, track_id)
            liked = True

        logger.info(
            "like_toggled",
            user_id=resolved_user_id,
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
        # Resolve user_id
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)
        
        if not user:
            return [], 0

        offset = (page - 1) * size
        tracks, total = await self._repo.list_liked_tracks(
            user_id=user.id, offset=offset, limit=size
        )
        logger.info(
            "liked_tracks_listed",
            user_id=user.id,
            total=total,
        )
        return tracks, total

    async def is_liked(
        self, user_id: int, track_id: int
    ) -> bool:
        like = await self._repo.get(user_id, track_id)
        return like is not None
