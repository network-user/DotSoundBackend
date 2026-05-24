from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lyrics_job import LyricsJob
from app.models.user import User
from app.repositories.admin_lyrics_timecode_sync import (
    AdminLyricsTimecodeSyncRepository,
    TimecodeSyncMode,
)
from app.services.audio_compute_admin_service import (
    AudioComputeAdminService,
)
from app.services.lyrics_service import LyricsService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_TERMINAL = frozenset({"done", "succeeded", "failed", "error", "cancelled"})


def _serialize_job_row(
    job: LyricsJob,
    *,
    labels: dict[int, dict[str, str | None]],
) -> dict[str, Any]:
    track_id = int(job.track_id)
    meta = labels.get(track_id, {})
    return {
        "id": job.id,
        "track_id": track_id,
        "track_title": meta.get("title"),
        "track_artist": meta.get("artist"),
        "status": job.status,
        "profile": job.profile,
        "queue_priority": int(job.queue_priority or 0),
        "current_tier": job.current_tier,
        "error": job.error,
        "attempts": int(job.attempts or 0),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "duration_ms": job.duration_ms,
        "progress_id": job.progress_id,
        "request_with_sync": bool(job.request_with_sync),
        "sync_mode": (
            "resync_existing" if job.request_bypass_cache else "unsynced"
        ),
    }


class AdminLyricsTimecodeSyncService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AdminLyricsTimecodeSyncRepository(session)

    async def get_overview(
        self,
        *,
        requested_by_user_id: int | None = None,
        since: datetime | None = None,
    ) -> dict[str, Any]:
        try:
            jobs = await self._repo.list_align_jobs(
                limit=250,
                requested_by_user_id=requested_by_user_id,
                since=since,
            )
        except Exception as exc:
            logger.exception(
                "admin_timecode_sync_list_jobs_failed",
                requested_by_user_id=requested_by_user_id,
                since=since.isoformat() if since else None,
                error_type=type(exc).__name__,
            )
            raise
        try:
            candidate_counts = await self._repo.candidate_counts()
        except Exception as exc:
            logger.exception(
                "admin_timecode_sync_count_candidates_failed",
                error_type=type(exc).__name__,
            )
            raise
        running = next(
            (j for j in jobs if j.status == "running"),
            None,
        )
        queued = [j for j in jobs if j.status == "queued"]
        next_job = queued[0] if queued else None
        recent = sorted(
            (j for j in jobs if j.status in _TERMINAL),
            key=lambda j: (j.finished_at or j.created_at,),
            reverse=True,
        )[:80]
        track_ids = list(
            {int(j.track_id) for j in jobs if j.track_id is not None}
        )
        labels = await self._repo.track_labels(track_ids)
        return {
            "filters": {
                "requested_by_user_id": requested_by_user_id,
                "since": (since.isoformat() if since is not None else None),
            },
            "candidate_count": candidate_counts["unsynced"],
            "candidate_counts": candidate_counts,
            "counts": {
                "queued": len(queued),
                "running": 1 if running else 0,
                "recent_terminal": len(recent),
            },
            "running": (
                _serialize_job_row(running, labels=labels) if running else None
            ),
            "next": (
                _serialize_job_row(next_job, labels=labels)
                if next_job
                else None
            ),
            "queued": [_serialize_job_row(j, labels=labels) for j in queued],
            "recent": [_serialize_job_row(j, labels=labels) for j in recent],
        }

    async def enqueue(
        self,
        admin: User,
        *,
        track_ids: list[int] | None,
        enqueue_all_unsynced: bool,
        limit: int,
        mode: TimecodeSyncMode = "unsynced",
    ) -> dict[str, Any]:
        lim = max(1, min(500, int(limit)))
        if enqueue_all_unsynced:
            targets = await self._repo.list_candidate_targets(
                mode=mode,
                limit=lim,
            )
        elif track_ids:
            targets = await self._repo.list_candidate_targets(
                mode=mode,
                limit=lim,
                track_ids=track_ids,
            )
        else:
            return {
                "requested": 0,
                "enqueued": 0,
                "skipped": 0,
                "job_ids": [],
            }

        svc = LyricsService(self._session)
        enqueued = 0
        skipped = 0
        job_ids: list[str] = []
        for track_id, target_mode in targets:
            progress_id = await svc.enqueue_background_lyrics(
                track_id,
                requested_by_user_id=admin.id,
                with_sync=True,
                bypass_cache=False,
                force_sync_existing_text=True,
                force_resync_existing_sync=(target_mode == "resync_existing"),
            )
            if progress_id:
                enqueued += 1
                job_id = await self._repo.job_id_by_progress(progress_id)
                if job_id:
                    job_ids.append(job_id)
            else:
                skipped += 1
        logger.info(
            "admin_timecode_sync_enqueue",
            requested=len(targets),
            enqueued=enqueued,
            skipped=skipped,
            admin_id=admin.id,
            mode=mode,
        )
        return {
            "requested": len(targets),
            "enqueued": enqueued,
            "skipped": skipped,
            "job_ids": job_ids,
        }

    async def set_priority(
        self,
        job_id: str,
        *,
        queue_priority: int | None,
        bump_next: bool,
    ) -> dict[str, Any]:
        job = await self._repo.get_align_job(job_id)
        if job is None:
            return {}
        if bump_next:
            queue_priority = (await self._repo.max_queued_align_priority()) + 1
        if queue_priority is None:
            raise ValueError("priority_required")
        compute = AudioComputeAdminService(self._session)
        out = await compute.update_lyrics_job_routing(
            job_id,
            pinned_worker_id=job.pinned_worker_id,
            queue_priority=int(queue_priority),
        )
        if out is None:
            return {}
        refreshed = await self._repo.get_align_job(job_id)
        if refreshed is None:
            return out
        labels = await self._repo.track_labels([int(refreshed.track_id)])
        return _serialize_job_row(
            refreshed,
            labels=labels,
        )

    async def cancel_job(self, job_id: str) -> dict[str, Any] | None:
        job = await self._repo.get_align_job(job_id)
        if job is None:
            return None
        from app.services.lyrics_job_cancel import (
            cancel_lyrics_job_for_admin,
        )

        return await cancel_lyrics_job_for_admin(
            self._session,
            job_id,
        )
