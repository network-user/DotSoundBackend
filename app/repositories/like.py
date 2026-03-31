import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.like import Like
from app.models.track import Track

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class LikeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self, user_id: int, track_id: int
    ) -> Like | None:
        result = await self._session.execute(
            select(Like).where(
                Like.user_id == user_id,
                Like.track_id == track_id,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, user_id: int, track_id: int) -> Like:
        like = Like(user_id=user_id, track_id=track_id)
        self._session.add(like)
        await self._session.flush()
        logger.debug(
            "db_like_added",
            user_id=user_id,
            track_id=track_id,
        )
        return like

    async def remove(
        self, user_id: int, track_id: int
    ) -> bool:
        result = await self._session.execute(
            delete(Like).where(
                Like.user_id == user_id,
                Like.track_id == track_id,
            )
        )
        removed = result.rowcount > 0
        logger.debug(
            "db_like_removed",
            user_id=user_id,
            track_id=track_id,
            found=removed,
        )
        return removed

    async def list_liked_tracks(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Track], int]:
        from sqlalchemy import func

        count_result = await self._session.execute(
            select(func.count())
            .select_from(Like)
            .where(
                Like.user_id == user_id,
                Track.is_active.is_(True),
            )
            .join(Track, Track.id == Like.track_id)
        )
        total = count_result.scalar_one()

        tracks_result = await self._session.execute(
            select(Track)
            .join(Like, Like.track_id == Track.id)
            .where(
                Like.user_id == user_id,
                Track.is_active.is_(True),
            )
            .order_by(Like.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        logger.debug(
            "db_liked_tracks_listed",
            user_id=user_id,
            total=total,
        )
        return list(tracks_result.scalars().all()), total

    async def count_likes_for_user_tracks(self, user_id: int) -> int:
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count())
            .select_from(Like)
            .join(Track, Track.id == Like.track_id)
            .where(Track.uploaded_by_id == user_id, Track.is_active.is_(True))
        )
        return result.scalar_one()
