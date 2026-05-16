"""Service layer that backs the admin REST API.

Wraps :class:`app.repositories.admin.AdminRepository` and adds the
small bits of business logic that used to be inlined into the
admin route handlers (S3 cleanup on track delete, structured logs,
soft-validation on PATCHes).
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.models.complaint import Complaint
from app.models.track import Track
from app.models.user import User
from app.repositories.admin import AdminRepository
from app.schemas.admin_playback import (
    AdminPlaybackRepairBulkResponse,
    AdminPlaybackRepairEnqueueResponse,
    AdminPlaybackVerifyResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _diag_str(value: object, max_len: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned[:max_len]


def _diag_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _diag_protocols(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    protocols: list[str] = []
    for item in value[:5]:
        if isinstance(item, str) and item.strip():
            protocols.append(item.strip()[:40])
    return protocols


def _parse_playback_detail(raw: str | None) -> dict[str, object]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    result: dict[str, object] = {}
    code = _diag_str(parsed.get("code"), 96)
    reason = _diag_str(parsed.get("reason"), 160)
    stage = _diag_str(parsed.get("stage"), 96)
    upstream_status = _diag_int(parsed.get("upstream_status"))
    attempted_protocols = _diag_protocols(
        parsed.get("attempted_protocols"),
    )
    if code:
        result["playback_last_error_code"] = code
    if reason:
        result["playback_last_error_reason"] = reason
    if stage:
        result["playback_last_error_stage"] = stage
    if upstream_status is not None:
        result["playback_last_upstream_status"] = upstream_status
    if attempted_protocols:
        result["playback_last_attempted_protocols"] = attempted_protocols
    return result


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
        lyrics_catalog_miss_only: bool = False,
        search: str | None = None,
        for_playlist_owner_id: int | None = None,
        playable_only: bool = False,
    ) -> tuple[list[Track], int]:
        return await self._repo.list_tracks(
            page=page,
            size=size,
            is_active=is_active,
            without_lyrics=without_lyrics,
            lyrics_catalog_miss_only=lyrics_catalog_miss_only,
            search=search,
            for_playlist_owner_id=for_playlist_owner_id,
            playable_only=playable_only,
        )

    async def list_track_ids(
        self,
        *,
        is_active: bool | None = None,
        without_lyrics: bool = False,
        lyrics_catalog_miss_only: bool = False,
        search: str | None = None,
        for_playlist_owner_id: int | None = None,
        playable_only: bool = False,
    ) -> tuple[list[int], int]:
        return await self._repo.list_track_ids(
            is_active=is_active,
            without_lyrics=without_lyrics,
            lyrics_catalog_miss_only=lyrics_catalog_miss_only,
            search=search,
            for_playlist_owner_id=for_playlist_owner_id,
            playable_only=playable_only,
        )

    async def list_tracks_playback_unavailable(
        self,
        *,
        page: int,
        size: int,
        search: str | None,
        playback_error: str | None = None,
    ) -> tuple[list[Track], int]:
        return await self._repo.list_tracks_playback_unavailable(
            page=page,
            size=size,
            search=search,
            playback_error=playback_error,
        )

    async def list_track_ids_playback_unavailable(
        self,
        *,
        search: str | None,
        playback_error: str | None = None,
    ) -> tuple[list[int], int]:
        return await self._repo.list_track_ids_playback_unavailable(
            search=search,
            playback_error=playback_error,
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

    async def get_playback_failure_diagnostics(
        self,
        track_ids: list[int],
    ) -> dict[int, dict[str, object]]:
        events = await self._repo.latest_track_playback_failure_events(
            track_ids,
        )
        return {
            track_id: parsed
            for track_id, event in events.items()
            if (
                parsed := _parse_playback_detail(
                    event.detail_truncated,
                )
            )
        }

    async def list_track_ids_playback_suppressed(
        self,
        *,
        search: str | None,
    ) -> tuple[list[int], int]:
        return await self._repo.list_track_ids_playback_suppressed(
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

    async def verify_track_playback(
        self,
        track_id: int,
    ) -> AdminPlaybackVerifyResponse | None:
        from fastapi import HTTPException

        from app.api.v1.tracks.playback import (
            _resolve_third_party_stream_with_recovery,
        )

        track = await self._repo.get_track(track_id)
        if track is None:
            return None
        if not track.is_active:
            return AdminPlaybackVerifyResponse(
                ok=False,
                detail="Track is inactive",
            )
        if track.access_mode == "third_party_stream":
            try:
                (
                    eff,
                    _url,
                    protocol,
                ) = await _resolve_third_party_stream_with_recovery(
                    track,
                    self._session,
                    use_cache=False,
                )
                eid = int(getattr(eff, "id", track_id))
                return AdminPlaybackVerifyResponse(
                    ok=True,
                    detail="Third-party stream resolves",
                    effective_track_id=eid,
                    stream_protocol=protocol,
                )
            except HTTPException as exc:
                det = exc.detail
                text = det if isinstance(det, str) else str(det)
                return AdminPlaybackVerifyResponse(
                    ok=False,
                    detail=text,
                    http_status=exc.status_code,
                )

        if track.file_key:
            return AdminPlaybackVerifyResponse(
                ok=True,
                detail="Internal track: file_key present",
                stream_protocol="direct",
            )

        return AdminPlaybackVerifyResponse(
            ok=False,
            detail="Internal track has no file_key",
        )

    async def enqueue_track_playback_repair(
        self,
        track_id: int,
        *,
        actor_id: int,
        force_requeue: bool = False,
    ) -> AdminPlaybackRepairEnqueueResponse | None:
        track = await self._repo.get_track(track_id)
        if track is None:
            return None

        from app.services import playback_repair_progress as progress
        from app.services.background_jobs import (
            IdempotencySkipped,
            enqueue,
        )
        from app.services.playback_repair_worker import (
            repair_track_playback_task,
        )

        progress_id = progress.new_progress_id()
        await progress.safe_set_progress(
            progress_id,
            stage="queued",
            track_id=track_id,
            log_line="queued by admin",
        )
        try:
            job_id = await enqueue(
                repair_track_playback_task,
                payload={
                    "track_id": track_id,
                    "progress_id": progress_id,
                    "bypass_refresh_cache": True,
                },
                queue="default",
                max_attempts=2,
                idempotency_key=(
                    None
                    if force_requeue
                    else f"playback-repair:track:{track_id}"
                ),
                idempotency_ttl_seconds=600,
                created_by_user_id=actor_id,
                job_id_payload_key="background_job_id",
            )
        except IdempotencySkipped:
            await progress.safe_set_progress(
                progress_id,
                stage="skipped",
                track_id=track_id,
                log_line="playback repair is already queued",
            )
            return AdminPlaybackRepairEnqueueResponse(
                queued=False,
                track_id=track_id,
                detail="Playback repair is already queued",
            )
        return AdminPlaybackRepairEnqueueResponse(
            queued=True,
            track_id=track_id,
            job_id=job_id,
            progress_id=progress_id,
            detail="Playback repair queued",
        )

    async def enqueue_tracks_playback_repair(
        self,
        track_ids: list[int],
        *,
        actor_id: int,
        force_requeue: bool = False,
    ) -> AdminPlaybackRepairBulkResponse:
        unique_ids = list(dict.fromkeys(track_ids))
        queued = 0
        skipped = 0
        missing = 0
        job_ids: list[str] = []
        progress_ids: list[str] = []
        for track_id in unique_ids:
            result = await self.enqueue_track_playback_repair(
                track_id,
                actor_id=actor_id,
                force_requeue=force_requeue,
            )
            if result is None:
                missing += 1
            elif result.queued:
                queued += 1
                if result.job_id is not None:
                    job_ids.append(result.job_id)
                if result.progress_id is not None:
                    progress_ids.append(result.progress_id)
            else:
                skipped += 1
        return AdminPlaybackRepairBulkResponse(
            requested=len(unique_ids),
            queued=queued,
            skipped=skipped,
            missing=missing,
            job_ids=job_ids,
            progress_ids=progress_ids,
            detail=(
                f"Playback repair queued={queued}, "
                f"skipped={skipped}, missing={missing}"
            ),
        )

    async def clear_track_playback_diagnostics(
        self,
        track_id: int,
    ) -> Track | None:
        track = await self._repo.get_track(track_id)
        if track is None:
            return None
        track.playback_last_failure_at = None
        track.playback_last_http_status = None
        track.playback_last_failure_source = None
        track.playback_recovery_failed_at = None
        await self._session.flush()
        return track

    async def full_restore_track_playback_health(
        self,
        track_id: int,
    ) -> Track | None:
        track = await self._repo.get_track(track_id)
        if track is None:
            return None
        track.playback_suppressed_until = None
        track.playback_last_failure_at = None
        track.playback_last_http_status = None
        track.playback_last_failure_source = None
        track.playback_recovery_failed_at = None
        await self._session.flush()
        return track

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

    async def delete_track(
        self,
        track_id: int,
        *,
        actor_id: int,
        reason: str = "admin",
    ) -> bool:
        """Admin-side soft-delete.

        Tracks are moved to "trash" with ``deleted_at = now()``
        and ``deleted_reason = reason`` (``admin`` by default,
        ``dmca`` for rights-holder takedowns). External assets
        survive until the daily hard-delete cron processes the
        per-reason grace period from PrivateCore.
        """
        from app.repositories.track import TrackRepository
        from app.services.search_index_notify import (
            schedule_delete_track,
        )

        repo = TrackRepository(self._session)
        track = await repo.admin_soft_delete(
            track_id, by_user_id=actor_id, reason=reason
        )
        if track is None:
            return False
        await schedule_delete_track(track_id)
        return True

    async def restore_track(self, track_id: int) -> Track | None:
        from app.repositories.track import TrackRepository
        from app.services.search_index_notify import (
            schedule_reindex_track,
        )

        repo = TrackRepository(self._session)
        track = await repo.admin_restore(track_id)
        if track is None:
            return None
        await schedule_reindex_track(track_id)
        return track

    async def hard_delete_track_now(
        self, track_id: int, *, actor_id: int
    ) -> bool:
        """Bypass grace period and wipe the track immediately."""
        from app.services.track_hard_delete_service import (
            TrackHardDeleteService,
        )

        svc = TrackHardDeleteService(self._session)
        return await svc.hard_delete_one(track_id, actor_id=actor_id)

    async def list_deleted_tracks(
        self,
        *,
        page: int,
        size: int,
        search: str | None = None,
    ) -> tuple[list[Track], int]:
        from app.repositories.track import TrackRepository

        repo = TrackRepository(self._session)
        offset = (page - 1) * size
        return await repo.list_admin_deleted(
            offset=offset, limit=size, search=search
        )

    async def list_deleted_track_ids(
        self,
        *,
        search: str | None = None,
    ) -> tuple[list[int], int]:
        from app.repositories.track import TrackRepository

        repo = TrackRepository(self._session)
        return await repo.list_admin_deleted_ids(search=search)

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
        out = await repo.admin_update_track(track_id=track_id, **fields)
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

    async def list_deleted_users(
        self,
        *,
        page: int,
        size: int,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        return await self._repo.list_deleted_users(
            page=page, size=size, search=search
        )

    async def restore_user(self, user_id: int) -> User | None:
        from app.repositories.user import UserRepository

        return await UserRepository(self._session).restore(user_id)

    async def hard_delete_user_now(
        self, user_id: int, *, actor_id: int
    ) -> bool:
        """Bypass grace period and erase the user immediately.

        Mirrors the daily ``AccountDeletionService`` cron but
        for a single target after admin step-up confirm.
        """
        from sqlalchemy import delete as sa_delete

        from app.core import s3
        from app.models.admin_action_log import AdminActionLog
        from app.repositories.user import UserRepository

        user_repo = UserRepository(self._session)
        user = await user_repo.get_by_id(user_id)
        if user is None:
            return False
        avatar_key = user.avatar_key

        try:
            await self._session.execute(
                sa_delete(AdminActionLog).where(
                    AdminActionLog.user_id == user_id
                )
            )
            await self._session.flush()
        except Exception:
            logger.warning(
                "admin_user_hard_delete_log_purge_failed",
                user_id=user_id,
                actor_id=actor_id,
                exc_info=True,
            )

        ok = await user_repo.hard_delete(user_id)
        if ok and avatar_key:
            try:
                await s3.delete_object(avatar_key)
            except Exception:
                logger.warning(
                    "admin_user_hard_delete_avatar_cleanup_failed",
                    user_id=user_id,
                    avatar_key=avatar_key,
                    exc_info=True,
                )
        if ok:
            logger.info(
                "admin_user_hard_delete_done",
                user_id=user_id,
                actor_id=actor_id,
            )
        return ok

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
            track = await self._repo.get_track(complaint.track_id)
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
            raise AdminServiceError(f"unknown action: {action}")
        if note:
            comment = f"\n\n[moderator note " f"({action})]: {note}"
            complaint.reason = (complaint.reason + comment)[:6000]
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
