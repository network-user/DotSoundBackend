import structlog
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.like import Like
from app.models.track import Track
from app.models.user_track_library import UserTrackLibrary
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _result_rowcount(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


class UserTrackLibraryRepository:
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

    @staticmethod
    def _current_user_link_condition(user_id: int) -> ColumnElement[bool]:
        return and_(
            UserTrackLibrary.track_id == Track.id,
            UserTrackLibrary.user_id == user_id,
        )

    @staticmethod
    def _visible_to_library_owner(user_id: int) -> ColumnElement[bool]:
        return or_(
            UserTrackLibrary.user_id == user_id,
            and_(
                Track.uploaded_by_id == user_id,
                Track.catalog_type == "ugc",
            ),
        )

    @staticmethod
    def _library_import_condition() -> ColumnElement[bool]:
        return or_(
            Track.imported_from.isnot(None),
            and_(
                UserTrackLibrary.source.isnot(None),
                UserTrackLibrary.source != "upload",
            ),
        )

    async def add(
        self,
        user_id: int,
        track_id: int,
        source: str | None = None,
    ) -> bool:
        """Idempotent insert. Returns True if a new row was added,
        False if the link already existed (no-op).
        """
        stmt = (
            pg_insert(UserTrackLibrary)
            .values(
                user_id=user_id,
                track_id=track_id,
                source=source,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "track_id"])
        )
        result = await self._session.execute(stmt)
        added = _result_rowcount(result) > 0
        if added:
            logger.debug(
                "db_library_added",
                user_id=user_id,
                track_id=track_id,
                source=source,
            )
        return added

    async def remove(self, user_id: int, track_id: int) -> bool:
        result = await self._session.execute(
            delete(UserTrackLibrary).where(
                UserTrackLibrary.user_id == user_id,
                UserTrackLibrary.track_id == track_id,
            )
        )
        removed = _result_rowcount(result) > 0
        logger.debug(
            "db_library_removed",
            user_id=user_id,
            track_id=track_id,
            found=removed,
        )
        return removed

    async def list_by_user(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 50,
        playable_only: bool = False,
    ) -> tuple[list[Track], int]:
        count_stmt = (
            select(func.count(Track.id))
            .select_from(Track)
            .outerjoin(
                UserTrackLibrary,
                self._current_user_link_condition(user_id),
            )
            .where(
                self._visible_to_library_owner(user_id),
                Track.is_active.is_(True),
                self._exclude_hidden_sources(),
                TrackRepository._playback_listing_allowed(),
            )
        )
        if playable_only:
            count_stmt = count_stmt.where(
                (Track.file_key.isnot(None)) | (Track.sc_url.isnot(None))
            )
        total = (await self._session.execute(count_stmt)).scalar_one()

        list_stmt = (
            select(Track)
            .select_from(Track)
            .outerjoin(
                UserTrackLibrary,
                self._current_user_link_condition(user_id),
            )
            .where(
                self._visible_to_library_owner(user_id),
                Track.is_active.is_(True),
                self._exclude_hidden_sources(),
                TrackRepository._playback_listing_allowed(),
            )
        )
        if playable_only:
            list_stmt = list_stmt.where(
                (Track.file_key.isnot(None)) | (Track.sc_url.isnot(None))
            )
        list_stmt = (
            list_stmt.order_by(
                func.coalesce(
                    UserTrackLibrary.imported_at,
                    Track.created_at,
                ).desc()
            )
            .offset(offset)
            .limit(limit)
        )
        tracks = (await self._session.execute(list_stmt)).scalars().all()
        return list(tracks), int(total)

    async def list_liked_or_imported(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Track], int]:
        base = (
            Track.is_active.is_(True)
            & self._exclude_hidden_sources()
            & Track.deleted_at.is_(None)
        )
        liked_ids = (
            select(Track.id)
            .join(
                Like,
                (Like.track_id == Track.id)
                & (Like.user_id == user_id),
            )
            .where(base)
        )
        imported_ids = (
            select(Track.id)
            .join(
                UserTrackLibrary,
                UserTrackLibrary.track_id == Track.id,
            )
            .where(
                base,
                UserTrackLibrary.user_id == user_id,
                self._library_import_condition(),
            )
        )
        all_ids_subq = liked_ids.union(imported_ids).subquery()

        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(
                        all_ids_subq
                    )
                )
            ).scalar_one()
        )

        rows = await self._session.execute(
            select(Track)
            .where(Track.id.in_(select(all_ids_subq.c.id)))
            .order_by(Track.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows.scalars().all()), total

    async def count_by_user(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.count(Track.id))
            .select_from(Track)
            .outerjoin(
                UserTrackLibrary,
                self._current_user_link_condition(user_id),
            )
            .where(
                self._visible_to_library_owner(user_id),
                Track.is_active.is_(True),
                self._exclude_hidden_sources(),
                TrackRepository._playback_listing_allowed(),
            )
        )
        return int(result.scalar_one())

    async def has(self, user_id: int, track_id: int) -> bool:
        result = await self._session.execute(
            select(UserTrackLibrary.user_id).where(
                UserTrackLibrary.user_id == user_id,
                UserTrackLibrary.track_id == track_id,
            )
        )
        return result.first() is not None
