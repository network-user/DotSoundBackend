from __future__ import annotations

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.models.album import Album
from app.repositories.admin_album import AdminAlbumRepository
from app.repositories.album import AlbumRepository
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AdminAlbumService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._admin_repo = AdminAlbumRepository(session)
        self._album_repo = AlbumRepository(session)
        self._track_repo = TrackRepository(session)
        self._user_repo = UserRepository(session)

    async def list_albums(
        self,
        *,
        page: int,
        size: int,
        search: str | None,
    ) -> tuple[list[tuple[Album, int]], int]:
        return await self._admin_repo.list_albums(
            page=page,
            size=size,
            search=search,
        )

    async def get_detail(self, album_id: int) -> Album | None:
        return await self._admin_repo.get_with_tracks(album_id)

    async def update_metadata(
        self,
        album_id: int,
        *,
        title: str | None,
        description: str | None,
        is_public: bool | None,
        owner_id: int | None,
    ) -> Album | None:
        album = await self._album_repo.get_by_id(album_id)
        if not album:
            return None
        if owner_id is not None:
            owner = await self._user_repo.get_by_id(owner_id)
            if not owner:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Owner user not found",
                )
        await self._album_repo.update(
            album,
            title=title,
            description=description,
            is_public=is_public,
            owner_id=owner_id,
        )
        await self._session.commit()
        await self._session.refresh(album)
        return album

    async def upload_cover(
        self,
        album_id: int,
        *,
        data: bytes,
        content_type: str,
    ) -> Album | None:
        album = await self._album_repo.get_by_id(album_id)
        if not album:
            return None
        prev = album.cover_key
        key = await s3.upload_cover(
            data,
            content_type,
            user_id=album.owner_id,
            session=self._session,
        )
        await self._album_repo.update(album, cover_key=key)
        await self._session.commit()
        if prev and prev != key:
            try:
                await s3.delete_object(prev)
            except Exception:
                logger.warning(
                    "admin_album_cover_delete_failed",
                    album_id=album_id,
                    cover_key=prev,
                )
        await self._session.refresh(album)
        return album

    async def add_track(self, album_id: int, track_id: int) -> None:
        album = await self._album_repo.get_by_id(album_id)
        if not album:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Album not found",
            )
        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )
        if track.album_id == album_id:
            return
        if track.album_id is not None:
            await self._album_repo.remove_track(track)
        await self._album_repo.add_track(album_id, track)
        await self._session.commit()
        logger.info(
            "admin_album_track_added",
            album_id=album_id,
            track_id=track_id,
        )

    async def remove_track(self, album_id: int, track_id: int) -> None:
        track = await self._track_repo.get_by_id(track_id)
        if not track or track.album_id != album_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found in this album",
            )
        await self._album_repo.remove_track(track)
        await self._session.commit()
        logger.info(
            "admin_album_track_removed",
            album_id=album_id,
            track_id=track_id,
        )

    async def reorder_tracks(
        self,
        album_id: int,
        ordered_track_ids: list[int],
    ) -> None:
        album = await self._album_repo.get_by_id(album_id)
        if not album:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Album not found",
            )
        try:
            await self._album_repo.set_album_track_order(
                album_id,
                ordered_track_ids,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        await self._session.commit()
