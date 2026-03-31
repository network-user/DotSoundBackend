import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.repositories.follow import FollowRepository
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class FollowService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = FollowRepository(session)
        self._user_repo = UserRepository(session)
        self._track_repo = TrackRepository(session)
        self._session = session

    async def _resolve_user_id(self, user_id: int) -> int:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return user.id

    async def toggle(self, follower_id: int, following_id: int) -> bool:
        resolved_follower = await self._resolve_user_id(follower_id)
        resolved_following = await self._resolve_user_id(following_id)

        if resolved_follower == resolved_following:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot follow yourself",
            )

        existing = await self._repo.get(resolved_follower, resolved_following)
        if existing:
            await self._repo.remove(resolved_follower, resolved_following)
            await self._session.commit()
            logger.info(
                "unfollowed",
                follower_id=resolved_follower,
                following_id=resolved_following,
            )
            return False
        else:
            await self._repo.add(resolved_follower, resolved_following)
            await self._session.commit()
            logger.info(
                "followed",
                follower_id=resolved_follower,
                following_id=resolved_following,
            )
            return True

    async def list_followers(
        self, user_id: int, page: int = 1, size: int = 20
    ) -> tuple[list[User], int]:
        resolved = await self._resolve_user_id(user_id)
        offset = (page - 1) * size
        return await self._repo.list_followers(resolved, offset, size)

    async def list_following(
        self, user_id: int, page: int = 1, size: int = 20
    ) -> tuple[list[User], int]:
        resolved = await self._resolve_user_id(user_id)
        offset = (page - 1) * size
        return await self._repo.list_following(resolved, offset, size)

    async def get_feed(
        self, user_id: int, page: int = 1, size: int = 20
    ) -> tuple[list[Track], int]:
        resolved = await self._resolve_user_id(user_id)
        followed_ids = await self._repo.list_followed_user_ids(resolved)
        if not followed_ids:
            return [], 0
        offset = (page - 1) * size
        return await self._track_repo.list_by_users_public(
            followed_ids, offset, size
        )
