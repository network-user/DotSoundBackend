import structlog
from sqlalchemy import func, select
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
    ) -> Album:
        if title is not None:
            album.title = title
        if description is not None:
            album.description = description
        if is_public is not None:
            album.is_public = is_public
        await self._session.flush()
        await self._session.refresh(album)
        return album

    async def delete(self, album: Album) -> None:
        await self._session.delete(album)
        await self._session.flush()
        logger.debug("db_album_deleted", album_id=album.id)

    async def add_track(self, album_id: int, track: Track) -> None:
        track.album_id = album_id
        await self._session.flush()

    async def remove_track(self, track: Track) -> None:
        track.album_id = None
        await self._session.flush()
