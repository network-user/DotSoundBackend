"""Track hard-delete pipeline.

Runs once a day from the Taskiq scheduler (see migration
``0087_track_soft_delete_and_admin_log_index``). Picks up tracks
whose ``deleted_at`` has crossed the per-reason grace period
encoded in PrivateCore (``track_lifecycle_policy``) and removes
them irreversibly: S3 assets, audio-blob ref, ES document,
database row.

Restore is impossible past this point -- which is exactly what
the user accepted in the soft-delete confirmation dialog.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.models.track import Track
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class TrackHardDeleteService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TrackRepository(session)

    async def hard_delete_expired_tracks(
        self,
        *,
        now: datetime | None = None,
        batch_limit: int | None = None,
    ) -> dict[str, Any]:
        from app.services.track_lifecycle_adapter import (
            TRACK_HARD_DELETE_BATCH_LIMIT,
            should_hard_delete_track,
        )

        moment = now or datetime.now(UTC)
        limit = batch_limit or TRACK_HARD_DELETE_BATCH_LIMIT

        candidates = await self._repo.list_hard_delete_candidates(
            limit=limit
        )
        deleted: list[int] = []
        skipped: list[int] = []
        s3_failures: list[int] = []

        for track in candidates:
            if track.deleted_at is None:
                skipped.append(track.id)
                continue
            reason = track.deleted_reason or "owner"
            if not should_hard_delete_track(
                track.deleted_at, reason, now=moment
            ):
                skipped.append(track.id)
                continue

            track_id = track.id
            try:
                await self._purge_external_assets(track)
            except Exception:
                logger.exception(
                    "track_hard_delete_assets_failed",
                    track_id=track_id,
                )
                s3_failures.append(track_id)

            try:
                await self._notify_search_index(track_id)
            except Exception:
                logger.warning(
                    "track_hard_delete_search_notify_failed",
                    track_id=track_id,
                    exc_info=True,
                )

            try:
                ok = await self._repo.hard_delete_track(track_id)
            except Exception:
                logger.exception(
                    "track_hard_delete_db_failed",
                    track_id=track_id,
                )
                continue
            if ok:
                deleted.append(track_id)
            else:
                skipped.append(track_id)

        summary = {
            "scanned": len(candidates),
            "deleted": len(deleted),
            "skipped": len(skipped),
            "s3_failures": len(s3_failures),
            "moment": moment.isoformat(),
        }
        logger.info("track_hard_delete_summary", **summary)
        return summary

    async def hard_delete_one(
        self, track_id: int, *, actor_id: int | None = None
    ) -> bool:
        """Force hard-delete a single track regardless of grace.

        Used by admins via the explicit "Delete forever" button
        after step-up confirmation. The caller is responsible for
        the audit log entry (including ``actor_id``).
        """
        track = await self._repo.get_by_id(track_id)
        if track is None:
            return False
        try:
            await self._purge_external_assets(track)
        except Exception:
            logger.exception(
                "track_hard_delete_one_assets_failed",
                track_id=track_id,
            )
        try:
            await self._notify_search_index(track_id)
        except Exception:
            logger.warning(
                "track_hard_delete_one_search_notify_failed",
                track_id=track_id,
                exc_info=True,
            )
        ok = await self._repo.hard_delete_track(track_id)
        if ok:
            logger.info(
                "track_hard_delete_one_done",
                track_id=track_id,
                actor_id=actor_id,
            )
        return ok

    async def _purge_external_assets(self, track: Track) -> None:
        from app.services.audio_blob_service import (
            AudioBlobService,
        )

        blob_svc = AudioBlobService(self._session)
        await blob_svc.try_release_for_track(track)
        await self._session.refresh(track)

        track_id = track.id
        try:
            await s3.delete_objects_by_prefix(f"hls/{track_id}/")
        except Exception:
            logger.warning(
                "hard_delete_hls_prefix_failed",
                track_id=track_id,
                exc_info=True,
            )

        if not track.blob_id and track.file_key:
            await self._best_effort_delete(track_id, track.file_key)
        for key in (
            track.cover_key,
            track.video_key,
            track.video_thumbnail_key,
        ):
            if key:
                await self._best_effort_delete(track_id, key)

    async def _best_effort_delete(
        self, track_id: int, key: str
    ) -> None:
        try:
            await s3.delete_object(key)
        except Exception:
            logger.warning(
                "hard_delete_s3_object_failed",
                track_id=track_id,
                key=key,
                exc_info=True,
            )

    @staticmethod
    async def _notify_search_index(track_id: int) -> None:
        from app.services.search_index_notify import (
            schedule_delete_track,
        )

        await schedule_delete_track(track_id)
