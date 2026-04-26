import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.dislike import DislikeRepository
from app.repositories.like import LikeRepository
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class DislikeService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = DislikeRepository(session)
        self._like_repo = LikeRepository(session)
        self._track_repo = TrackRepository(session)
        self._user_repo = UserRepository(session)

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
            disliked = False
        else:
            # When disliking, remove like if it exists
            await self._like_repo.remove(resolved_user_id, track_id)
            await self._repo.add(resolved_user_id, track_id)
            disliked = True

        logger.info(
            "dislike_toggled",
            user_id=resolved_user_id,
            track_id=track_id,
            disliked=disliked,
        )
        return disliked

    async def is_disliked(
        self, user_id: int, track_id: int
    ) -> bool:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)
        
        if not user:
            return False
            
        dislike = await self._repo.get(user.id, track_id)
        return dislike is not None
