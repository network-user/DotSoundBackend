from datetime import datetime

import structlog
from sqlalchemy import and_, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.dislike import Dislike
from app.models.track import Track
from app.repositories.base import BaseRepository
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class DislikeRepository(BaseRepository[Dislike]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Dislike)

    @staticmethod
    def _exclude_hidden_sources() -> ColumnElement[bool]:
        hidden = ("youtube",)
        source_platform = func.lower(func.coalesce(Track.source_platform, ""))
        imported_from = func.lower(func.coalesce(Track.imported_from, ""))
        return (~source_platform.in_(hidden)) & (~imported_from.in_(hidden))

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

    async def get(self, user_id: int, track_id: int) -> Dislike | None:
        result = await self._session.execute(
            select(Dislike).where(
                Dislike.user_id == user_id,
                Dislike.track_id == track_id,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, user_id: int, track_id: int) -> Dislike:
        return await self.create(user_id=user_id, track_id=track_id)

    async def add_idempotent(
        self, user_id: int, track_id: int
    ) -> bool:
        stmt = (
            pg_insert(Dislike)
            .values(user_id=user_id, track_id=track_id)
            .on_conflict_do_nothing(
                index_elements=["user_id", "track_id"]
            )
        )
        result = await self._session.execute(stmt)
        return bool((getattr(result, "rowcount", 0) or 0) > 0)

    async def remove(self, user_id: int, track_id: int) -> bool:
        result = await self._session.execute(
            delete(Dislike).where(
                Dislike.user_id == user_id,
                Dislike.track_id == track_id,
            )
        )
        await self._session.flush()
        return bool((getattr(result, "rowcount", 0) or 0) > 0)

    async def exists_any_for_user_track_ids(
        self,
        user_id: int,
        track_ids: list[int],
    ) -> bool:
        if not track_ids:
            return False
        r = await self._session.execute(
            select(Dislike.track_id)
            .where(
                Dislike.user_id == user_id,
                Dislike.track_id.in_(track_ids),
            )
            .limit(1)
        )
        return r.scalar_one_or_none() is not None

    @staticmethod
    def _build_query_filter(
        q: str | None,
        base_clause: ColumnElement[bool],
    ) -> ColumnElement[bool]:
        if not q:
            return base_clause
        pattern = f"%{q.lower()}%"
        return and_(
            base_clause,
            func.lower(Track.title).like(pattern)
            | func.lower(func.coalesce(Track.artist, "")).like(
                pattern
            ),
        )

    async def list_disliked_tracks(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
        source_filter: str | None = None,
        query: str | None = None,
    ) -> tuple[list[tuple[Track, datetime]], int]:
        base_where = self._build_source_filter(
            source_filter,
            and_(
                Dislike.user_id == user_id,
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                self._exclude_hidden_sources(),
                TrackRepository._playback_listing_allowed(),
            ),
        )
        base_where = self._build_query_filter(
            query, base_where
        )

        count_result = await self._session.execute(
            select(func.count())
            .select_from(Dislike)
            .join(Track, Track.id == Dislike.track_id)
            .where(base_where)
        )
        total = count_result.scalar_one()

        tracks_result = await self._session.execute(
            select(Track, Dislike.created_at)
            .join(Dislike, Dislike.track_id == Track.id)
            .where(base_where)
            .order_by(Dislike.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = tracks_result.all()
        logger.debug(
            "db_disliked_tracks_listed",
            user_id=user_id,
            total=total,
        )
        return [(row[0], row[1]) for row in rows], total
