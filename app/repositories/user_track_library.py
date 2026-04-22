import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user_track_library import UserTrackLibrary

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class UserTrackLibraryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        added = bool(result.rowcount)
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
        removed = bool(result.rowcount)
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
            select(func.count())
            .select_from(UserTrackLibrary)
            .join(Track, Track.id == UserTrackLibrary.track_id)
            .where(
                UserTrackLibrary.user_id == user_id,
                Track.is_active.is_(True),
            )
        )
        if playable_only:
            count_stmt = count_stmt.where(
                (Track.file_key.isnot(None)) | (Track.sc_url.isnot(None))
            )
        total = (await self._session.execute(count_stmt)).scalar_one()

        list_stmt = (
            select(Track)
            .join(
                UserTrackLibrary,
                UserTrackLibrary.track_id == Track.id,
            )
            .where(
                UserTrackLibrary.user_id == user_id,
                Track.is_active.is_(True),
            )
        )
        if playable_only:
            list_stmt = list_stmt.where(
                (Track.file_key.isnot(None)) | (Track.sc_url.isnot(None))
            )
        list_stmt = (
            list_stmt.order_by(UserTrackLibrary.imported_at.desc())
            .offset(offset)
            .limit(limit)
        )
        tracks = (await self._session.execute(list_stmt)).scalars().all()
        return list(tracks), int(total)

    async def count_by_user(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(UserTrackLibrary)
            .join(Track, Track.id == UserTrackLibrary.track_id)
            .where(
                UserTrackLibrary.user_id == user_id,
                Track.is_active.is_(True),
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
