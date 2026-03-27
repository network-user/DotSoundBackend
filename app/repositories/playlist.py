import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playlist import Playlist, PlaylistTrack
from app.models.track import Track

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class PlaylistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self, playlist_id: int
    ) -> Playlist | None:
        return await self._session.get(Playlist, playlist_id)

    async def list_by_owner(
        self,
        owner_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Playlist], int]:
        from sqlalchemy import func

        total = (
            await self._session.execute(
                select(func.count()).where(
                    Playlist.owner_id == owner_id
                )
            )
        ).scalar_one()

        result = await self._session.execute(
            select(Playlist)
            .where(Playlist.owner_id == owner_id)
            .order_by(Playlist.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(
        self,
        name: str,
        owner_id: int,
        is_public: bool,
    ) -> Playlist:
        playlist = Playlist(
            name=name,
            owner_id=owner_id,
            is_public=is_public,
        )
        self._session.add(playlist)
        await self._session.flush()
        await self._session.refresh(playlist)
        logger.debug(
            "db_playlist_created",
            playlist_id=playlist.id,
            owner_id=owner_id,
        )
        return playlist

    async def update(
        self,
        playlist: Playlist,
        name: str | None,
        is_public: bool | None,
    ) -> Playlist:
        if name is not None:
            playlist.name = name
        if is_public is not None:
            playlist.is_public = is_public
        await self._session.flush()
        return playlist

    async def delete(self, playlist: Playlist) -> None:
        await self._session.delete(playlist)
        await self._session.flush()
        logger.debug(
            "db_playlist_deleted", playlist_id=playlist.id
        )

    async def add_track(
        self,
        playlist_id: int,
        track_id: int,
        position: int = 0,
    ) -> PlaylistTrack:
        existing = await self._session.execute(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == playlist_id,
                PlaylistTrack.track_id == track_id,
            )
        )
        if existing.scalar_one_or_none():
            logger.debug(
                "db_playlist_track_already_exists",
                playlist_id=playlist_id,
                track_id=track_id,
            )
            return existing.scalar_one()  # type: ignore[return-value]

        pt = PlaylistTrack(
            playlist_id=playlist_id,
            track_id=track_id,
            position=position,
        )
        self._session.add(pt)
        await self._session.flush()
        logger.debug(
            "db_playlist_track_added",
            playlist_id=playlist_id,
            track_id=track_id,
        )
        return pt

    async def remove_track(
        self, playlist_id: int, track_id: int
    ) -> bool:
        result = await self._session.execute(
            delete(PlaylistTrack).where(
                PlaylistTrack.playlist_id == playlist_id,
                PlaylistTrack.track_id == track_id,
            )
        )
        return result.rowcount > 0

    async def get_tracks(
        self, playlist_id: int
    ) -> list[Track]:
        result = await self._session.execute(
            select(Track)
            .join(
                PlaylistTrack,
                PlaylistTrack.track_id == Track.id,
            )
            .where(
                PlaylistTrack.playlist_id == playlist_id,
                Track.is_active.is_(True),
            )
            .order_by(PlaylistTrack.position)
        )
        return list(result.scalars().all())
