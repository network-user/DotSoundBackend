import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playlist import Playlist
from app.models.track import Track
from app.repositories.playlist import PlaylistRepository
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class PlaylistService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = PlaylistRepository(session)
        self._track_repo = TrackRepository(session)

    async def create(
        self,
        name: str,
        owner_id: int,
        is_public: bool = True,
    ) -> Playlist:
        playlist = await self._repo.create(
            name=name, owner_id=owner_id, is_public=is_public
        )
        logger.info(
            "playlist_created",
            playlist_id=playlist.id,
            owner_id=owner_id,
        )
        return playlist

    async def get(
        self, playlist_id: int
    ) -> Playlist | None:
        return await self._repo.get_by_id(playlist_id)

    async def list_by_owner(
        self,
        owner_id: int,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Playlist], int]:
        offset = (page - 1) * size
        return await self._repo.list_by_owner(
            owner_id=owner_id, offset=offset, limit=size
        )

    async def update(
        self,
        playlist_id: int,
        requester_id: int,
        name: str | None,
        is_public: bool | None,
    ) -> Playlist:
        playlist = await self._get_owned(
            playlist_id, requester_id
        )
        return await self._repo.update(
            playlist, name=name, is_public=is_public
        )

    async def delete(
        self, playlist_id: int, requester_id: int
    ) -> None:
        playlist = await self._get_owned(
            playlist_id, requester_id
        )
        await self._repo.delete(playlist)
        logger.info(
            "playlist_deleted",
            playlist_id=playlist_id,
            owner_id=requester_id,
        )

    async def add_track(
        self,
        playlist_id: int,
        track_id: int,
        requester_id: int,
        position: int = 0,
    ) -> None:
        await self._get_owned(playlist_id, requester_id)
        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )
        await self._repo.add_track(playlist_id, track_id, position)
        logger.info(
            "playlist_track_added",
            playlist_id=playlist_id,
            track_id=track_id,
        )

    async def remove_track(
        self,
        playlist_id: int,
        track_id: int,
        requester_id: int,
    ) -> None:
        await self._get_owned(playlist_id, requester_id)
        found = await self._repo.remove_track(
            playlist_id, track_id
        )
        if not found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not in playlist",
            )

    async def get_tracks(
        self, playlist_id: int
    ) -> list[Track]:
        await self._assert_exists(playlist_id)
        return await self._repo.get_tracks(playlist_id)

    async def _get_owned(
        self, playlist_id: int, requester_id: int
    ) -> Playlist:
        playlist = await self._repo.get_by_id(playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playlist not found",
            )
        if playlist.owner_id != requester_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not your playlist",
            )
        return playlist

    async def _assert_exists(
        self, playlist_id: int
    ) -> None:
        playlist = await self._repo.get_by_id(playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playlist not found",
            )
