import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.album import Album
from app.models.user import User
from app.repositories.album import AlbumRepository
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AlbumService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = AlbumRepository(session)
        self._track_repo = TrackRepository(session)
        self._user_repo = UserRepository(session)
        self._session = session

    async def _resolve_user(self, user_id: int) -> User | None:
        user = await self._user_repo.get_by_id(user_id)
        if user is not None:
            return user
        return await self._user_repo.get_by_telegram_id(user_id)

    async def _resolve_user_id(self, user_id: int) -> int:
        user = await self._resolve_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return user.id

    async def _get_owned_album(self, album_id: int, user_id: int) -> Album:
        album = await self._repo.get_by_id(album_id)
        if not album:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Album not found"
            )
        resolved = await self._resolve_user_id(user_id)
        if album.owner_id != resolved:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not the album owner",
            )
        return album

    async def _assert_admin_actor(self, user_id: int) -> None:
        actor = await self._resolve_user(user_id)
        if (
            actor is None
            or not actor.is_admin
            or not actor.is_active
            or not actor.admin_init
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )

    async def _get_manageable_album(
        self,
        album_id: int,
        user_id: int,
        *,
        allow_admin: bool = False,
    ) -> Album:
        album = await self._repo.get_by_id(album_id)
        if not album:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Album not found",
            )
        resolved = await self._resolve_user_id(user_id)
        if album.owner_id == resolved:
            return album
        if allow_admin:
            await self._assert_admin_actor(user_id)
            return album
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not the album owner",
        )

    async def create(
        self,
        user_id: int,
        title: str,
        description: str | None = None,
        is_public: bool = True,
    ) -> Album:
        resolved = await self._resolve_user_id(user_id)
        album = await self._repo.create(
            owner_id=resolved,
            title=title,
            description=description,
            is_public=is_public,
        )
        await self._session.commit()
        logger.info("album_created", album_id=album.id, owner_id=resolved)
        return album

    async def get_by_id(self, album_id: int) -> Album | None:
        return await self._repo.get_by_id(album_id)

    async def get_with_tracks(self, album_id: int) -> Album | None:
        return await self._repo.get_with_tracks(album_id)

    async def list_by_user(
        self, user_id: int, page: int = 1, size: int = 50
    ) -> tuple[list[Album], int]:
        resolved = await self._resolve_user_id(user_id)
        offset = (page - 1) * size
        return await self._repo.list_by_user(resolved, offset, size)

    async def update(
        self,
        album_id: int,
        user_id: int,
        title: str | None = None,
        description: str | None = None,
        is_public: bool | None = None,
        *,
        allow_admin: bool = False,
    ) -> Album:
        album = await self._get_manageable_album(
            album_id,
            user_id,
            allow_admin=allow_admin,
        )
        album = await self._repo.update(album, title, description, is_public)
        await self._session.commit()
        logger.info(
            "album_updated",
            album_id=album_id,
            actor_user_id=user_id,
            admin_override=allow_admin and album.owner_id != user_id,
        )
        return album

    async def delete(
        self,
        album_id: int,
        user_id: int,
        *,
        allow_admin: bool = False,
    ) -> None:
        album = await self._get_manageable_album(
            album_id,
            user_id,
            allow_admin=allow_admin,
        )
        await self._repo.delete(album)
        await self._session.commit()
        logger.info(
            "album_deleted",
            album_id=album_id,
            actor_user_id=user_id,
            admin_override=allow_admin and album.owner_id != user_id,
        )

    async def add_track(
        self,
        album_id: int,
        track_id: int,
        user_id: int,
        *,
        allow_admin: bool = False,
    ) -> None:
        album = await self._get_manageable_album(
            album_id,
            user_id,
            allow_admin=allow_admin,
        )
        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Track not found"
            )
        resolved = await self._resolve_user_id(user_id)
        if not allow_admin and track.uploaded_by_id != resolved:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only add own tracks to album",
            )
        if allow_admin and album.owner_id != resolved:
            await self._assert_admin_actor(user_id)
        if track.album_id == album.id:
            return
        if track.album_id is not None:
            await self._repo.remove_track(track)
        await self._repo.add_track(album.id, track)
        await self._session.commit()
        logger.info(
            "album_track_added",
            album_id=album_id,
            track_id=track_id,
            actor_user_id=user_id,
            admin_override=allow_admin and album.owner_id != user_id,
        )

    async def remove_track(
        self,
        album_id: int,
        track_id: int,
        user_id: int,
        *,
        allow_admin: bool = False,
    ) -> None:
        await self._get_manageable_album(
            album_id,
            user_id,
            allow_admin=allow_admin,
        )
        track = await self._track_repo.get_by_id(track_id)
        if not track or track.album_id != album_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found in this album",
            )
        await self._repo.remove_track(track)
        await self._session.commit()
        logger.info(
            "album_track_removed",
            album_id=album_id,
            track_id=track_id,
            actor_user_id=user_id,
        )

    async def reorder_tracks(
        self,
        album_id: int,
        track_ids: list[int],
        user_id: int,
        *,
        allow_admin: bool = False,
    ) -> None:
        await self._get_manageable_album(
            album_id,
            user_id,
            allow_admin=allow_admin,
        )
        try:
            await self._repo.set_album_track_order(album_id, track_ids)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        await self._session.commit()
        logger.info(
            "album_track_order_updated",
            album_id=album_id,
            actor_user_id=user_id,
        )
