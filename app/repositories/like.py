from datetime import datetime

import structlog
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.like import Like
from app.models.track import Track
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class LikeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _exclude_hidden_sources() -> ColumnElement[bool]:
        hidden = ("youtube",)
        source_platform = func.lower(
            func.coalesce(Track.source_platform, "")
        )
        imported_from = func.lower(
            func.coalesce(Track.imported_from, "")
        )
        return (~source_platform.in_(hidden)) & (
            ~imported_from.in_(hidden)
        )

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
        removed = bool((getattr(result, "rowcount", 0) or 0) > 0)
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
        source_filter: str | None = None,
    ) -> tuple[list[tuple[Track, datetime]], int]:
        base_where = self._build_source_filter(
            source_filter,
            and_(
                Like.user_id == user_id,
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                self._exclude_hidden_sources(),
                TrackRepository._playback_listing_allowed(),
            ),
        )

        count_result = await self._session.execute(
            select(func.count())
            .select_from(Like)
            .join(Track, Track.id == Like.track_id)
            .where(base_where)
        )
        total = count_result.scalar_one()

        tracks_result = await self._session.execute(
            select(Track, Like.created_at)
            .join(Like, Like.track_id == Track.id)
            .where(base_where)
            .order_by(Like.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = tracks_result.all()
        logger.debug(
            "db_liked_tracks_listed",
            user_id=user_id,
            total=total,
        )
        return [(row[0], row[1]) for row in rows], total

    @staticmethod
    def _build_source_filter(
        source_filter: str | None,
        base_clause: ColumnElement[bool],
    ) -> ColumnElement[bool]:
        if source_filter == "platform":
            return and_(base_clause, Track.catalog_type == "ugc")
        if source_filter == "soundcloud":
            return and_(base_clause, Track.source == "soundcloud")
        if source_filter == "other":
            return and_(
                base_clause,
                Track.catalog_type != "ugc",
                Track.source != "soundcloud",
            )
        return base_clause

    async def count_likes_for_user_tracks(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Like)
            .join(Track, Track.id == Like.track_id)
            .where(Track.uploaded_by_id == user_id, Track.is_active.is_(True))
            .where(self._exclude_hidden_sources())
        )
        return result.scalar_one()

    async def count_for_track(self, track_id: int) -> int:
        r = await self._session.execute(
            select(func.count())
            .select_from(Like)
            .where(Like.track_id == track_id)
        )
        return int(r.scalar_one())

    async def exists_any_for_user_track_ids(
        self,
        user_id: int,
        track_ids: list[int],
    ) -> bool:
        if not track_ids:
            return False
        r = await self._session.execute(
            select(Like.track_id).where(
                Like.user_id == user_id,
                Like.track_id.in_(track_ids),
            ).limit(1)
        )
        return r.scalar_one_or_none() is not None
