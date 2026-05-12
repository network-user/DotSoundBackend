import asyncio
import secrets
from typing import Final

import structlog
from dotsound_private_core.services.playlist_cover_policy import (
    PLAYLIST_COLLAGE_GRID_SIDE,
    playlist_collage_cell_count,
    should_attempt_auto_playlist_cover,
    utcnow,
)
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.models.playlist import Playlist
from app.models.playlist_collab import PlaylistCollaborator
from app.models.track import Track
from app.models.user import User
from app.repositories.playlist import PlaylistRepository
from app.repositories.playlist_collab import PlaylistCollabRepository
from app.repositories.user import UserRepository
from app.services.playlist_cover_collage import (
    build_playlist_cover_collage_webp,
)
from app.services.playlist_track_eligibility import (
    ensure_track_addable_to_user_playlist,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_UNSET: Final[object] = object()


class PlaylistService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = PlaylistRepository(session)
        self._cr = PlaylistCollabRepository(session)
        self._user_repo = UserRepository(session)

    async def create(
        self,
        name: str,
        owner_id: int,
        is_public: bool = True,
        description: str | None = None,
    ) -> Playlist:
        user = await self._resolve_user(owner_id)
        playlist = await self._repo.create(
            name=name,
            owner_id=user.id,
            is_public=is_public,
            description=description,
        )
        logger.info(
            "playlist_created",
            playlist_id=playlist.id,
            owner_id=user.id,
        )
        return playlist

    async def get(self, playlist_id: int) -> Playlist | None:
        return await self._repo.get_by_id(playlist_id)

    async def list_by_owner(
        self,
        owner_id: int,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[tuple[Playlist, int]], int]:
        user = await self._resolve_user(owner_id)
        offset = (page - 1) * size
        return await self._repo.list_by_owner(
            owner_id=user.id, offset=offset, limit=size
        )

    async def update(
        self,
        playlist_id: int,
        requester_id: int,
        name: str | None,
        is_public: bool | None,
        description: object = _UNSET,
        *,
        allow_admin: bool = False,
    ) -> Playlist:
        playlist = await self._get_can_manage(
            playlist_id,
            requester_id,
            allow_admin=allow_admin,
        )
        return await self._repo.update(
            playlist,
            name=name,
            is_public=is_public,
            description=description,
        )

    async def delete(
        self,
        playlist_id: int,
        requester_id: int,
        *,
        allow_admin: bool = False,
    ) -> None:
        playlist = await self._get_can_manage(
            playlist_id,
            requester_id,
            allow_admin=allow_admin,
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
        *,
        allow_admin: bool = False,
    ) -> None:
        playlist = await self._get_can_write(
            playlist_id,
            requester_id,
            allow_admin=allow_admin,
        )
        await ensure_track_addable_to_user_playlist(
            self._session,
            track_id=track_id,
            playlist_owner_id=playlist.owner_id,
        )
        await self._repo.add_track(playlist_id, track_id, position)
        await self._maybe_generate_collage_cover(playlist_id)
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
        *,
        allow_admin: bool = False,
    ) -> None:
        await self._get_can_write(
            playlist_id,
            requester_id,
            allow_admin=allow_admin,
        )
        found = await self._repo.remove_track(playlist_id, track_id)
        if not found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not in playlist",
            )

    async def reorder_tracks(
        self,
        playlist_id: int,
        ordered_track_ids: list[int],
        requester_id: int,
        *,
        allow_admin: bool = False,
    ) -> None:
        await self._get_can_write(
            playlist_id,
            requester_id,
            allow_admin=allow_admin,
        )
        try:
            await self._repo.set_track_order(
                playlist_id,
                ordered_track_ids,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        await self._maybe_generate_collage_cover(playlist_id)

    async def get_tracks(self, playlist_id: int) -> list[Track]:
        await self._assert_exists(playlist_id)
        return await self._repo.get_tracks(playlist_id)

    async def list_featured(self, limit: int = 20) -> list[Playlist]:
        return await self._repo.list_featured(limit=limit)

    async def list_featured_with_tracks(
        self, limit: int = 20
    ) -> list[tuple[Playlist, list[Track]]]:
        """Featured playlists with their tracks in a single batch query."""
        playlists = await self._repo.list_featured(limit=limit)
        if not playlists:
            return []
        tracks_by_id = await self._repo.get_tracks_bulk(
            [p.id for p in playlists]
        )
        return [(p, tracks_by_id.get(p.id, [])) for p in playlists]

    async def search_public(
        self,
        query: str,
        page: int = 1,
        size: int = 20,
        exclude_owner_id: int | None = None,
    ) -> tuple[list[Playlist], int]:
        offset = (page - 1) * size
        return await self._repo.search_public(
            query=query,
            offset=offset,
            limit=size,
            exclude_owner_id=exclude_owner_id,
        )

    async def get_collaborators(
        self,
        playlist_id: int,
        requester_id: int,
        *,
        allow_admin: bool = False,
    ) -> list[dict]:
        await self._get_can_manage(
            playlist_id,
            requester_id,
            allow_admin=allow_admin,
        )
        rows = await self._cr.list_with_users(playlist_id)
        return [
            {
                "user_id": collab.user_id,
                "role": collab.role,
                "username": user.username,
                "display_name": user.display_name
                or user.first_name,
                "created_at": collab.created_at,
            }
            for collab, user in rows
        ]

    async def remove_collaborator(
        self,
        playlist_id: int,
        target_user_id: int,
        requester_id: int,
        *,
        allow_admin: bool = False,
    ) -> None:
        await self._get_can_manage(
            playlist_id,
            requester_id,
            allow_admin=allow_admin,
        )
        removed = await self._cr.remove(playlist_id, target_user_id)
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collaborator not found",
            )
        await self._session.commit()
        logger.info(
            "playlist_collaborator_removed",
            playlist_id=playlist_id,
            target_user_id=target_user_id,
        )

    async def upload_owner_cover(
        self,
        playlist_id: int,
        *,
        requester_id: int,
        data: bytes,
        content_type: str,
    ) -> Playlist:
        playlist = await self._get_owned(
            playlist_id,
            requester_id,
        )
        actor = await self._resolve_user(requester_id)
        old_key = playlist.cover_key
        key = await s3.upload_cover(
            data,
            content_type,
            user_id=actor.id,
            session=self._session,
        )
        playlist.cover_key = key
        playlist.cover_auto_suppressed = False
        await self._session.flush()
        if old_key and old_key != key:
            try:
                await s3.delete_object(old_key)
            except Exception:
                logger.warning(
                    "playlist_cover_old_delete_failed",
                    playlist_id=playlist_id,
                    cover_key=old_key,
                )
        return playlist

    async def delete_owner_cover(
        self,
        playlist_id: int,
        requester_id: int,
    ) -> Playlist:
        playlist = await self._get_owned(
            playlist_id,
            requester_id,
        )
        if playlist.cover_key:
            prev = playlist.cover_key
            try:
                await s3.delete_object(prev)
            except Exception:
                logger.warning(
                    "playlist_cover_delete_object_failed",
                    playlist_id=playlist_id,
                    cover_key=prev,
                )
        playlist.cover_key = None
        playlist.cover_auto_suppressed = True
        await self._session.flush()
        return playlist

    async def _maybe_generate_collage_cover(
        self,
        playlist_id: int,
    ) -> None:
        pl = await self._repo.get_by_id(playlist_id)
        if not pl:
            return
        n_visible = await self._repo.count_visible_tracks(
            playlist_id,
        )
        if not should_attempt_auto_playlist_cover(
            playlist_type=pl.playlist_type,
            cover_auto_suppressed=pl.cover_auto_suppressed,
            collage_generated_at=pl.collage_generated_at,
            cover_key=pl.cover_key,
            visible_track_count=n_visible,
        ):
            return
        cells = playlist_collage_cell_count()
        tracks = await self._repo.get_tracks(playlist_id)
        rng = secrets.SystemRandom()
        pool = list(tracks)
        rng.shuffle(pool)
        picked = pool[:cells]
        raws: list[bytes | None] = []
        for t in picked:
            if not t.cover_key:
                raws.append(None)
                continue
            try:
                blob = await s3.download_object(t.cover_key)
                raws.append(blob)
            except Exception:
                logger.warning(
                    "playlist_collage_track_cover_miss",
                    track_id=t.id,
                    playlist_id=playlist_id,
                )
                raws.append(None)
        while len(raws) < cells:
            raws.append(None)
        try:
            webp = await asyncio.to_thread(
                build_playlist_cover_collage_webp,
                raws,
                grid_side=PLAYLIST_COLLAGE_GRID_SIDE,
            )
        except Exception:
            logger.exception(
                "playlist_collage_render_failed",
                playlist_id=playlist_id,
            )
            return
        key = f"playlist-covers/{pl.owner_id}/{playlist_id}.webp"
        try:
            await s3.upload_object(key, webp, "image/webp")
        except Exception:
            logger.exception(
                "playlist_collage_upload_failed",
                playlist_id=playlist_id,
            )
            return
        pl.cover_key = key
        pl.collage_generated_at = utcnow()
        await self._session.flush()
        logger.info(
            "playlist_collage_generated",
            playlist_id=playlist_id,
            cover_key=key,
        )

    async def _get_owned(
        self, playlist_id: int, requester_id: int
    ) -> Playlist:
        user = await self._resolve_user(requester_id)
        playlist = await self._repo.get_by_id(playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playlist not found",
            )
        if playlist.owner_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not your playlist",
            )
        return playlist

    async def _assert_admin_actor(self, requester_id: int) -> None:
        user = await self._resolve_user(requester_id)
        if not user.is_admin or not user.is_active or not user.admin_init:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )

    async def _get_can_manage(
        self,
        playlist_id: int,
        requester_id: int,
        *,
        allow_admin: bool = False,
    ) -> Playlist:
        user = await self._resolve_user(requester_id)
        playlist = await self._repo.get_by_id(playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playlist not found",
            )
        if playlist.owner_id == user.id:
            return playlist
        if allow_admin:
            await self._assert_admin_actor(requester_id)
            return playlist
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your playlist",
        )

    async def _get_can_write(
        self,
        playlist_id: int,
        requester_id: int,
        *,
        allow_admin: bool = False,
    ) -> Playlist:
        user = await self._resolve_user(requester_id)
        playlist = await self._repo.get_by_id(playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playlist not found",
            )
        if playlist.owner_id == user.id:
            return playlist
        if allow_admin:
            await self._assert_admin_actor(requester_id)
            return playlist
        r = await self._session.execute(
            select(PlaylistCollaborator)
            .where(
                (PlaylistCollaborator.playlist_id == playlist_id)
                & (PlaylistCollaborator.user_id == user.id)
                & (PlaylistCollaborator.role == "editor")
            )
            .limit(1)
        )
        row = r.scalars().first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not your playlist",
            )
        return playlist

    async def _assert_exists(self, playlist_id: int) -> None:
        playlist = await self._repo.get_by_id(playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playlist not found",
            )

    async def _resolve_user(self, user_id: int) -> User:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user
