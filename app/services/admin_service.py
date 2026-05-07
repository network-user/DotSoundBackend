"""Service layer that backs the admin REST API.

Wraps :class:`app.repositories.admin.AdminRepository` and adds the
small bits of business logic that used to be inlined into the
admin route handlers (S3 cleanup on track delete, structured logs,
soft-validation on PATCHes).
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.models.complaint import Complaint
from app.models.track import Track
from app.models.user import User
from app.repositories.admin import AdminRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AdminServiceError(Exception):
    pass


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AdminRepository(session)

    async def list_tracks(
        self,
        *,
        page: int,
        size: int,
        is_active: bool | None = None,
        without_lyrics: bool = False,
        search: str | None = None,
    ) -> tuple[list[Track], int]:
        return await self._repo.list_tracks(
            page=page,
            size=size,
            is_active=is_active,
            without_lyrics=without_lyrics,
            search=search,
        )

    async def list_tracks_playback_unavailable(
        self,
        *,
        page: int,
        size: int,
        search: str | None,
    ) -> tuple[list[Track], int]:
        return await self._repo.list_tracks_playback_unavailable(
            page=page,
            size=size,
            search=search,
        )

    async def list_tracks_playback_suppressed(
        self,
        *,
        page: int,
        size: int,
        search: str | None,
    ) -> tuple[list[Track], int]:
        return await self._repo.list_tracks_playback_suppressed(
            page=page,
            size=size,
            search=search,
        )

    async def clear_track_playback_suppression(
        self,
        track_id: int,
    ) -> Track | None:
        from app.services.track_playback_health_service import (
            TrackPlaybackHealthService,
        )

        svc = TrackPlaybackHealthService(self._session)
        return await svc.clear_auto_suppression(track_id)

    async def list_tracks_for_artist(
        self,
        artist_id: int,
        *,
        page: int,
        size: int,
        search: str | None = None,
    ) -> tuple[list[Track], int]:
        return await self._repo.list_tracks_for_artist(
            artist_id,
            page=page,
            size=size,
            search=search,
        )

    async def get_track(self, track_id: int) -> Track | None:
        return await self._repo.get_track(track_id)

    async def delete_track(self, track_id: int) -> bool:
        from app.services.audio_blob_service import (
            AudioBlobService,
        )

        track = await self._repo.get_track(track_id)
        if track is None:
            return False
        ab = AudioBlobService(self._session)
        await ab.try_release_for_track(track)
        await self._session.refresh(track)
        try:
            await s3.delete_objects_by_prefix(
                f"hls/{track_id}/"
            )
        except Exception:
            logger.warning(
                "admin_hls_prefix_delete_failed",
                track_id=track_id,
            )
        if not track.blob_id and track.file_key:
            try:
                await s3.delete_object(track.file_key)
            except Exception:
                logger.warning(
                    "admin_s3_delete_failed",
                    track_id=track_id,
                    file_key=track.file_key,
                )
        if track.cover_key:
            try:
                await s3.delete_object(track.cover_key)
            except Exception:
                logger.warning(
                    "admin_s3_cover_delete_failed",
                    track_id=track_id,
                    cover_key=track.cover_key,
                )
        await self._session.delete(track)
        return True

    async def upload_track_cover(
        self,
        track_id: int,
        *,
        data: bytes,
        content_type: str,
        admin_user_id: int,
    ) -> Track | None:
        from app.services.search_index_notify import (
            schedule_reindex_track,
        )

        track = await self._repo.get_track(track_id)
        if track is None:
            return None
        old = track.cover_key
        key = await s3.upload_cover(
            data,
            content_type,
            user_id=admin_user_id,
            session=self._session,
        )
        track.cover_key = key
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(track)
        if old and old != key:
            try:
                await s3.delete_object(old)
            except Exception:
                logger.warning(
                    "admin_track_cover_old_delete_failed",
                    track_id=track_id,
                    cover_key=old,
                )
        try:
            await schedule_reindex_track(track.id)
        except Exception:
            logger.warning(
                "admin_track_cover_reindex_failed",
                track_id=track_id,
            )
        return track

    async def update_track(
        self,
        track_id: int,
        **fields: object,
    ) -> Track | None:
        from app.repositories.track import TrackRepository
        from app.services.search_index_notify import (
            schedule_reindex_track,
        )

        repo = TrackRepository(self._session)
        out = await repo.admin_update_track(
            track_id=track_id, **fields
        )
        if out:
            await schedule_reindex_track(out.id)
        return out

    async def set_track_visibility(
        self, track_id: int, is_active: bool
    ) -> Track | None:
        from app.services.audio_blob_service import (
            AudioBlobService,
        )

        track = await self._repo.get_track(track_id)
        if track is None:
            return None
        was_active = track.is_active
        track.is_active = is_active
        if was_active and not is_active:
            ab = AudioBlobService(self._session)
            await ab.try_release_for_track(track)
        await self._session.flush()
        return track

    async def list_users(
        self,
        *,
        page: int,
        size: int,
        is_active: bool | None = None,
        is_admin: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        return await self._repo.list_users(
            page=page,
            size=size,
            is_active=is_active,
            is_admin=is_admin,
            search=search,
        )

    async def update_user(
        self,
        user_id: int,
        *,
        display_name: str | None,
        is_active: bool | None,
        is_admin: bool | None,
    ) -> User | None:
        user = await self._repo.get_user(user_id)
        if user is None:
            return None
        if display_name is not None:
            user.display_name = display_name
        if is_active is not None:
            user.is_active = is_active
        if is_admin is not None:
            user.is_admin = is_admin
        await self._session.flush()
        return user

    async def list_complaints(
        self,
        *,
        page: int,
        size: int,
        unresolved_only: bool = False,
    ) -> tuple[list[Complaint], int]:
        return await self._repo.list_complaints(
            page=page,
            size=size,
            unresolved_only=unresolved_only,
        )

    async def resolve_complaint(self, complaint_id: int) -> Complaint | None:
        complaint = await self._repo.get_complaint(complaint_id)
        if complaint is None:
            return None
        complaint.is_resolved = True
        await self._session.flush()
        return complaint

    async def apply_complaint_action(
        self,
        complaint_id: int,
        action: str,
        note: str | None = None,
    ) -> tuple[Complaint, bool] | None:
        """Apply admin action to a complaint.

        Returns (complaint, track_hidden) on success, None when
        the complaint does not exist. Side effects:

        - 'accept' -> hides the track + marks complaint resolved
        - 'dismiss' -> marks complaint resolved
        - 'in_progress' -> leaves status unchanged

        The note (if provided) is appended to the reason as a
        moderator comment so it survives in the existing
        complaint row without a schema migration.
        """
        complaint = await self._repo.get_complaint(complaint_id)
        if complaint is None:
            return None
        track_hidden = False
        if action == "accept":
            complaint.is_resolved = True
            track = await self._repo.get_track(
                complaint.track_id
            )
            if track is not None and track.is_active:
                track.is_active = False
                from app.services.audio_blob_service import (
                    AudioBlobService,
                )

                ab = AudioBlobService(self._session)
                await ab.try_release_for_track(track)
                track_hidden = True
        elif action == "dismiss":
            complaint.is_resolved = True
        elif action == "in_progress":
            pass
        else:
            raise AdminServiceError(
                f"unknown action: {action}"
            )
        if note:
            comment = (
                f"\n\n[moderator note "
                f"({action})]: {note}"
            )
            complaint.reason = (
                complaint.reason + comment
            )[:6000]
        await self._session.flush()
        return complaint, track_hidden

    async def delete_complaint(self, complaint_id: int) -> bool:
        complaint = await self._repo.get_complaint(complaint_id)
        if complaint is None:
            return False
        await self._session.delete(complaint)
        return True

    async def get_popular_genres(
        self, limit: int = 20
    ) -> list[dict[str, Any]]:
        return await self._repo.get_popular_genres(limit)
