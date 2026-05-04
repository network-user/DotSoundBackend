from __future__ import annotations

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playlist import Playlist
from app.models.track import Track
from app.repositories.playlist import PlaylistRepository
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AdminPlaylistService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = PlaylistRepository(session)
        self._track_repo = TrackRepository(session)
        self._user_repo = UserRepository(session)

    async def list_playlists(
        self,
        *,
        page: int,
        size: int,
        search: str | None,
    ) -> tuple[list[tuple[Playlist, int]], int]:
        return await self._repo.list_for_admin(
            page=page,
            size=size,
            search=search,
        )

    async def get_detail(self, playlist_id: int) -> Playlist | None:
        return await self._repo.get_by_id(playlist_id)

    async def get_tracks_raw(
        self,
        playlist_id: int,
    ) -> list[Track]:
        return await self._repo.get_tracks(playlist_id)

    async def update_metadata(
        self,
        playlist_id: int,
        *,
        name: str | None,
        is_public: bool | None,
        owner_id: int | None,
    ) -> Playlist | None:
        playlist = await self._repo.get_by_id(playlist_id)
        if not playlist:
            return None
        if owner_id is not None:
            owner = await self._user_repo.get_by_id(owner_id)
            if not owner:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Owner user not found",
                )
        await self._repo.update(
            playlist,
            name=name,
            is_public=is_public,
            owner_id=owner_id,
        )
        await self._session.commit()
        await self._session.refresh(playlist)
        return playlist

    async def add_track(self, playlist_id: int, track_id: int) -> None:
        playlist = await self._repo.get_by_id(playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playlist not found",
            )
        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )
        inserted = await self._repo.add_track_at_end(
            playlist_id,
            track_id,
        )
        if not inserted:
            return
        await self._session.commit()
        logger.info(
            "admin_playlist_track_added",
            playlist_id=playlist_id,
            track_id=track_id,
        )

    async def remove_track(self, playlist_id: int, track_id: int) -> None:
        removed = await self._repo.remove_track(playlist_id, track_id)
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not in playlist",
            )
        await self._session.commit()
        logger.info(
            "admin_playlist_track_removed",
            playlist_id=playlist_id,
            track_id=track_id,
        )

    async def reorder_tracks(
        self,
        playlist_id: int,
        ordered_track_ids: list[int],
    ) -> None:
        playlist = await self._repo.get_by_id(playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playlist not found",
            )
        try:
            await self._repo.set_track_order(
                playlist_id,
                ordered_track_ids,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        await self._session.commit()
