import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.schemas.user import TrackStatsItem, UserStatsResponse

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_TOP_TRACKS_LIMIT = 5


class StatsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_author_stats(
        self, user_id: int
    ) -> UserStatsResponse:
        logger.info(
            "stats_requested", user_id=user_id
        )

        # Resolve user_id: could be internal ID or Telegram ID
        user_result = await self._session.execute(
            select(User.id).where(
                (User.id == user_id) | (User.telegram_id == user_id)
            )
        )
        resolved_id = user_result.scalar_one_or_none()
        
        if not resolved_id:
            logger.warning("stats_user_not_found", user_id=user_id)
            return UserStatsResponse(
                user_id=user_id,
                total_tracks=0,
                total_plays=0,
                top_tracks=[],
            )

        count_result = await self._session.execute(
            select(func.count(), func.coalesce(func.sum(Track.play_count), 0))
            .where(
                Track.uploaded_by_id == resolved_id,
                Track.is_active.is_(True),
            )
        )
        total_tracks, total_plays = count_result.one()

        top_result = await self._session.execute(
            select(Track)
            .where(
                Track.uploaded_by_id == resolved_id,
                Track.is_active.is_(True),
            )
            .order_by(Track.play_count.desc())
            .limit(_TOP_TRACKS_LIMIT)
        )
        top_tracks = [
            TrackStatsItem.model_validate(t)
            for t in top_result.scalars().all()
        ]

        logger.info(
            "stats_computed",
            user_id=user_id,
            total_tracks=total_tracks,
            total_plays=total_plays,
        )
        return UserStatsResponse(
            user_id=resolved_id,
            total_tracks=total_tracks,
            total_plays=int(total_plays),
            top_tracks=top_tracks,
        )
