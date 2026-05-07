from __future__ import annotations

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playlist import (
    PLAYLIST_TYPE_EDITORIAL,
    PLAYLIST_TYPE_IMPORTED_SC,
    Playlist,
)
from app.models.track import Track
from app.repositories.playlist import PlaylistRepository
from app.repositories.user import UserRepository
from app.services.playlist_track_eligibility import (
    ensure_track_addable_to_user_playlist,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AdminPlaylistService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = PlaylistRepository(session)
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
        is_featured: bool | None = None,
        description: str | None = None,
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
            is_featured=is_featured,
            description=description,
        )
        await self._session.commit()
        await self._session.refresh(playlist)
        return playlist

    async def create_editorial(
        self,
        *,
        name: str,
        owner_id: int,
        description: str | None,
        is_featured: bool,
        is_public: bool,
    ) -> Playlist:
        playlist = await self._repo.create(
            name=name,
            owner_id=owner_id,
            is_public=is_public,
            playlist_type=PLAYLIST_TYPE_EDITORIAL,
            is_featured=is_featured,
            description=description,
        )
        await self._session.commit()
        await self._session.refresh(playlist)
        logger.info(
            "admin_editorial_playlist_created",
            playlist_id=playlist.id,
            name=name,
            is_featured=is_featured,
        )
        return playlist

    async def import_from_sc_url(
        self,
        *,
        sc_service: object,
        source_url: str,
        name: str | None,
        owner_id: int,
        make_featured: bool,
        make_public: bool,
    ) -> Playlist:
        from app.services.soundcloud_service import (  # noqa: PLC0415
            SoundCloudService,
        )

        svc = sc_service
        if not isinstance(svc, SoundCloudService):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud not configured",
            )

        resolved = await svc.resolve_url(source_url)
        kind = resolved.get("kind", "")
        if kind not in ("playlist", "system-playlist"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "URL must point to a SoundCloud playlist, "
                    f"got kind={kind!r}"
                ),
            )

        playlist_name = name or resolved.get("title", "Imported Playlist")
        artwork_url = resolved.get("artwork_url")
        cover_key = await svc.download_artwork_as_cover_key(
            artwork_url, uploader_id=owner_id
        )

        tracks_data = resolved.get("tracks", [])
        if not tracks_data:
            tracks_data = await svc.expand_playlist_stub_tracks(
                int(resolved["id"]), tracks_data
            )

        playlist = await self._repo.create(
            name=playlist_name,
            owner_id=owner_id,
            is_public=make_public,
            playlist_type=PLAYLIST_TYPE_IMPORTED_SC,
            is_featured=make_featured,
            source_url=source_url,
            cover_key=cover_key,
            description=resolved.get("description") or None,
        )

        imported_count = 0
        for track_data in tracks_data:
            sc_url = track_data.get("permalink_url")
            if not sc_url:
                continue
            try:
                track = await svc.import_or_get_track(
                    sc_url,
                    uploader_id=owner_id,
                    auto_enqueue=False,
                )
                await self._repo.add_track_at_end(playlist.id, track.id)
                imported_count += 1
            except Exception:
                logger.warning(
                    "sc_playlist_track_import_failed",
                    sc_url=sc_url,
                )

        await self._session.commit()
        await self._session.refresh(playlist)
        logger.info(
            "admin_playlist_imported_from_sc",
            playlist_id=playlist.id,
            imported_tracks=imported_count,
            source_url=source_url,
        )
        return playlist

    async def add_track(self, playlist_id: int, track_id: int) -> None:
        playlist = await self._repo.get_by_id(playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playlist not found",
            )
        await ensure_track_addable_to_user_playlist(
            self._session,
            track_id=track_id,
            playlist_owner_id=playlist.owner_id,
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
