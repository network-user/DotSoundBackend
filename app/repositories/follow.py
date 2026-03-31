import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.follow import UserFollow
from app.models.user import User

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class FollowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self, follower_id: int, following_id: int
    ) -> UserFollow | None:
        result = await self._session.execute(
            select(UserFollow).where(
                UserFollow.follower_id == follower_id,
                UserFollow.following_id == following_id,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, follower_id: int, following_id: int) -> UserFollow:
        follow = UserFollow(follower_id=follower_id, following_id=following_id)
        self._session.add(follow)
        await self._session.flush()
        logger.debug(
            "db_follow_added",
            follower_id=follower_id,
            following_id=following_id,
        )
        return follow

    async def remove(self, follower_id: int, following_id: int) -> bool:
        result = await self._session.execute(
            delete(UserFollow).where(
                UserFollow.follower_id == follower_id,
                UserFollow.following_id == following_id,
            )
        )
        removed = result.rowcount > 0
        logger.debug(
            "db_follow_removed",
            follower_id=follower_id,
            following_id=following_id,
            found=removed,
        )
        return removed

    async def list_followers(
        self, user_id: int, offset: int = 0, limit: int = 20
    ) -> tuple[list[User], int]:
        condition = UserFollow.following_id == user_id
        count_result = await self._session.execute(
            select(func.count()).select_from(UserFollow).where(condition)
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            select(User)
            .join(UserFollow, UserFollow.follower_id == User.id)
            .where(condition)
            .order_by(UserFollow.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_following(
        self, user_id: int, offset: int = 0, limit: int = 20
    ) -> tuple[list[User], int]:
        condition = UserFollow.follower_id == user_id
        count_result = await self._session.execute(
            select(func.count()).select_from(UserFollow).where(condition)
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            select(User)
            .join(UserFollow, UserFollow.following_id == User.id)
            .where(condition)
            .order_by(UserFollow.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def count_followers(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(UserFollow)
            .where(UserFollow.following_id == user_id)
        )
        return result.scalar_one()

    async def count_following(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(UserFollow)
            .where(UserFollow.follower_id == user_id)
        )
        return result.scalar_one()

    async def list_followed_user_ids(self, user_id: int) -> list[int]:
        result = await self._session.execute(
            select(UserFollow.following_id).where(
                UserFollow.follower_id == user_id
            )
        )
        return list(result.scalars().all())
