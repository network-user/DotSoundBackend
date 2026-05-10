import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.repositories.follow import FollowRepository
from app.repositories.like import LikeRepository
from app.repositories.signal import ListenEventRepository
from app.repositories.track import TrackRepository
from app.schemas.user import TrackStatsItem, UserStatsResponse

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_TOP_TRACKS_LIMIT = 5


class StatsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._like_repo = LikeRepository(session)
        self._follow_repo = FollowRepository(session)
        self._listen_repo = ListenEventRepository(session)
        self._track_repo = TrackRepository(session)

    async def get_user_top_tracks(
        self, user_id: int, *, window: str
    ) -> tuple[list[Track], str]:
        from dotsound_private_core.services.user_top_policy import (
            MAX_TOP_TRACKS,
            TrackAggregate,
            normalize_window,
            rank_user_top_tracks,
        )

        window = normalize_window(window)
        since = ListenEventRepository.window_to_since(window)
        rows = await self._listen_repo.aggregate_user_top_tracks(
            user_id, since=since
        )
        ranked = rank_user_top_tracks(
            [
                TrackAggregate(
                    track_id=tid,
                    completed_listens=completed,
                    likes=likes,
                )
                for (tid, completed, likes) in rows
            ],
            limit=MAX_TOP_TRACKS,
        )
        track_ids = [int(r.key) for r in ranked]
        tracks = await self._track_repo.get_by_ids_preserve_order(
            track_ids
        )
        return tracks, window

    async def get_user_minutes_by_day(
        self, user_id: int, *, days: int
    ) -> list[tuple[str, int]]:
        """Return per-day listening minutes for the last ``days`` days."""
        from datetime import UTC, datetime, timedelta

        bounded = max(1, min(days, 90))
        since = datetime.now(UTC) - timedelta(days=bounded)
        return await self._listen_repo.aggregate_user_minutes_by_day(
            user_id, since=since
        )

    async def get_user_top_genres(
        self, user_id: int, *, window: str
    ) -> tuple[list[tuple[str, int]], str]:
        from dotsound_private_core.services.user_top_policy import (
            MAX_TOP_GENRES,
            GenreAggregate,
            normalize_window,
            rank_user_top_genres,
        )

        window = normalize_window(window)
        since = ListenEventRepository.window_to_since(window)
        rows = await self._listen_repo.aggregate_user_top_genres(
            user_id, since=since
        )
        score_by_genre = {g: c for (g, c) in rows}
        ranked = rank_user_top_genres(
            [
                GenreAggregate(genre=g, completed_listens=c)
                for (g, c) in rows
            ],
            limit=MAX_TOP_GENRES,
        )
        return (
            [
                (str(r.key), score_by_genre.get(str(r.key), 0))
                for r in ranked
            ],
            window,
        )

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

        total_likes = await self._like_repo.count_likes_for_user_tracks(
            resolved_id
        )
        followers_count = await self._follow_repo.count_followers(resolved_id)
        following_count = await self._follow_repo.count_following(resolved_id)

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
            total_likes=total_likes,
            followers_count=followers_count,
            following_count=following_count,
            top_tracks=top_tracks,
        )
