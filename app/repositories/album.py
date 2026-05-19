import structlog
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.album import Album
from app.models.track import Track

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AlbumRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        owner_id: int,
        title: str,
        description: str | None = None,
        is_public: bool = True,
    ) -> Album:
        album = Album(
            owner_id=owner_id,
            title=title,
            description=description,
            is_public=is_public,
        )
        self._session.add(album)
        await self._session.flush()
        await self._session.refresh(album)
        logger.debug("db_album_created", album_id=album.id)
        return album

    async def get_by_id(self, album_id: int) -> Album | None:
        result = await self._session.execute(
            select(Album).where(Album.id == album_id)
        )
        return result.scalar_one_or_none()

    async def get_with_tracks(self, album_id: int) -> Album | None:
        result = await self._session.execute(
            select(Album)
            .options(selectinload(Album.tracks))
            .where(Album.id == album_id)
        )
        return result.scalar_one_or_none()

    async def list_tracks_page(
        self,
        album_id: int,
        offset: int,
        limit: int,
        *,
        include_suppressed: bool,
    ) -> tuple[list[Track], int]:
        condition = Track.album_id == album_id
        if not include_suppressed:
            condition = condition & (
                Track.playback_suppressed_until.is_(None)
                | (Track.playback_suppressed_until <= func.now())
            )

        total_result = await self._session.execute(
            select(func.count(Track.id)).where(condition)
        )
        total = int(total_result.scalar_one())
        result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(
                Track.album_position.asc().nulls_last(),
                Track.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_tracks_cursor(
        self,
        album_id: int,
        *,
        cursor_position: int | None,
        cursor_track_id: int | None,
        limit: int,
        include_suppressed: bool,
    ) -> tuple[list[tuple[Track, int, int]], int, bool]:
        condition = Track.album_id == album_id
        if not include_suppressed:
            condition = condition & (
                Track.playback_suppressed_until.is_(None)
                | (Track.playback_suppressed_until <= func.now())
            )

        total_result = await self._session.execute(
            select(func.count(Track.id)).where(condition)
        )
        total = int(total_result.scalar_one())
        position = func.coalesce(Track.album_position, 2147483647)
        if cursor_position is not None and cursor_track_id is not None:
            condition = condition & or_(
                position > cursor_position,
                and_(
                    position == cursor_position,
                    Track.id > cursor_track_id,
                ),
            )
        result = await self._session.execute(
            select(Track, position.label("position"), Track.id)
            .where(condition)
            .order_by(
                Track.album_position.asc().nulls_last(),
                Track.id.asc(),
            )
            .limit(limit + 1)
        )
        rows = [
            (row[0], int(row[1]), int(row[2]))
            for row in result.all()
        ]
        return rows[:limit], total, len(rows) > limit

    async def list_by_user(
        self, user_id: int, offset: int = 0, limit: int = 50
    ) -> tuple[list[Album], int]:
        condition = Album.owner_id == user_id
        count_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            select(Album)
            .where(condition)
            .order_by(Album.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(
        self,
        album: Album,
        title: str | None = None,
        description: str | None = None,
        is_public: bool | None = None,
        cover_key: str | None = None,
        owner_id: int | None = None,
        clear_description: bool = False,
    ) -> Album:
        if title is not None:
            album.title = title
        if description is not None or clear_description:
            album.description = description
        if is_public is not None:
            album.is_public = is_public
        if cover_key is not None:
            album.cover_key = cover_key
        if owner_id is not None:
            album.owner_id = owner_id
        await self._session.flush()
        await self._session.refresh(album)
        return album

    async def delete(self, album: Album) -> None:
        await self._session.delete(album)
        await self._session.flush()
        logger.debug("db_album_deleted", album_id=album.id)

    async def _next_album_position(self, album_id: int) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(Track.album_position), -1)).where(
                Track.album_id == album_id,
            )
        )
        current_max = result.scalar_one()
        if current_max is None:
            return 0
        return int(current_max) + 1

    async def add_track(self, album_id: int, track: Track) -> None:
        track.album_id = album_id
        track.album_position = await self._next_album_position(album_id)
        await self._session.flush()

    async def remove_track(self, track: Track) -> None:
        album_id = track.album_id
        track.album_id = None
        track.album_position = None
        await self._session.flush()
        if album_id is not None:
            await self.compact_album_positions(album_id)

    async def compact_album_positions(self, album_id: int) -> None:
        result = await self._session.execute(
            select(Track)
            .where(Track.album_id == album_id)
            .order_by(
                Track.album_position.asc().nulls_last(),
                Track.id.asc(),
            )
        )
        rows = list(result.scalars().all())
        for pos, row in enumerate(rows):
            if row.album_position != pos:
                row.album_position = pos
        await self._session.flush()

    async def set_album_track_order(
        self,
        album_id: int,
        ordered_track_ids: list[int],
    ) -> None:
        result = await self._session.execute(
            select(Track).where(Track.album_id == album_id)
        )
        rows = {t.id: t for t in result.scalars().all()}
        if set(ordered_track_ids) != set(rows.keys()):
            raise ValueError(
                "track_ids must list every album track exactly once",
            )
        if len(ordered_track_ids) != len(rows):
            raise ValueError(
                "track_ids must list every album track exactly once",
            )
        for pos, tid in enumerate(ordered_track_ids):
            rows[tid].album_position = pos
        await self._session.flush()
