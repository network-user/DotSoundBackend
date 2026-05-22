"""Admin task-management endpoints (Taskiq + lyrics_jobs)."""

from __future__ import annotations

import contextlib
from typing import Any

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.dependencies import (
    get_db,
    require_capability,
    require_step_up,
)
from app.models.background_job import BackgroundJob
from app.models.scheduled_job import ScheduledJob
from app.models.track import Track
from app.models.user import User
from app.repositories.admin_action_log import AdminActionLogRepository
from app.repositories.admin_tasks import AdminTasksRepository
from app.services import compute_queue_service as q
from app.services.cancellation import signal_cancel

router = APIRouter(prefix="/tasks", tags=["admin-tasks"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_COMPUTE_JOB_LABELS: dict[str, str] = {
    q.JOB_TRACK_AUDIO_FEATURES: ("Audio analysis & 15s preview clip"),
    q.JOB_CATALOG_INGEST_NORMALIZE: ("Catalog ingest / normalization"),
    q.JOB_ARTIST_FEATURES_UPDATE: "Artist audio profile update",
    q.JOB_ARTIST_SIMILARITY_INDEX: "Artist similarity index",
    q.JOB_TRACK_SIMILARITY_INDEX: "Track similarity index",
}

ALLOWED_TASK_NAMES: frozenset[str] = frozenset(
    {
        "transcode_and_upload",
        "transcode_hls_only",
        "refresh_tor_list",
        "transcode_video",
        "generate_lyrics_task",
        "enqueue_artist_lyrics_task",
        "lyrics_discovery_sweep_task",
        "generate_and_upload_cover",
        "admin.alert.send",
        "normalize_track_titles_batch",
        "hls_renormalize_batch_task",
        "renormalize_track_hls_task",
    }
)

_PLAYBACK_REPAIR_TASK_NAME = (
    "app.services.playback_repair_worker:repair_track_playback_task"
)
_ACTIVE_BACKGROUND_JOB_STATUSES: frozenset[str] = frozenset(
    {"queued", "running", "cancelling"}
)
_TERMINAL_BACKGROUND_JOB_STATUSES: frozenset[str] = frozenset(
    {"done", "failed", "failed_terminal", "cancelled"}
)
_PLAYBACK_REPAIR_OUTCOMES: frozenset[str] = frozenset(
    {
        "repaired",
        "unresolved",
        "skipped",
        "not_found",
        "error",
        "cancelled",
    }
)
_PLAYBACK_REPAIR_SUMMARY_LIMIT = 20000


class BackgroundJobBulkCancelRequest(BaseModel):
    name: str | None = Field(default=None, max_length=96)
    queue: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, max_length=24)
    scheduled_job_id: str | None = Field(default=None, max_length=64)


class BackgroundJobBulkCancelResponse(BaseModel):
    matched: int
    cancelled: int
    cancelling: int
    purged_messages: int
    items: list[str]


class PlaybackRepairSummaryRequest(BaseModel):
    job_ids: list[str] = Field(default_factory=list)


class PlaybackRepairRetryUnresolvedRequest(BaseModel):
    job_ids: list[str] = Field(default_factory=list)


@router.post("/artist-stats-snapshot")
async def trigger_artist_stats_snapshot(
    _admin: User = Depends(require_capability("tasks.run")),
) -> dict[str, str]:
    from app.services.artist_stats_worker import (
        snapshot_monthly_artist_stats_task,
    )

    result = await snapshot_monthly_artist_stats_task.kiq()
    task_id = getattr(result, "task_id", None)
    return {"task_id": task_id}


@router.post("/text-censor-backfill")
async def trigger_text_censor_backfill(
    _admin: User = Depends(require_capability("tasks.run")),
) -> dict[str, str]:
    from app.tasks.text_censor_backfill import (
        text_censor_backfill_task,
    )

    result = await text_censor_backfill_task.kiq()
    task_id = getattr(result, "task_id", None)
    return {"task_id": task_id}


@router.post("/normalize-track-titles")
async def trigger_title_normalization(
    offset: int = Query(0, ge=0),
    batch_size: int = Query(200, ge=10, le=1000),
    _admin: User = Depends(require_capability("tasks.run")),
) -> dict[str, Any]:
    """Queue one batch of the retroactive title-artist normalization.

    Chain batches by incrementing ``offset`` by ``batch_size`` until
    the response contains ``"done": true``.
    """
    from app.services.track_title_normalization_task import (
        normalize_track_titles_batch,
    )

    result = await normalize_track_titles_batch.kiq(
        offset=offset, batch_size=batch_size
    )
    task_id = getattr(result, "task_id", None)
    return {"task_id": task_id, "offset": offset, "batch_size": batch_size}


@router.post("/hls-renormalize")
async def trigger_hls_renormalize_batch(
    offset: int = Query(0, ge=0),
    batch_size: int = Query(50, ge=1, le=500),
    _admin: User = Depends(require_capability("tasks.run")),
) -> dict[str, Any]:
    """Dispatch a batch of HLS re-transcode jobs with loudness normalization.

    Chain batches by incrementing ``offset`` by ``batch_size`` until
    the response contains ``"done": true``.
    """
    from app.services.hls_renormalize_task import hls_renormalize_batch_task

    result = await hls_renormalize_batch_task.kiq(
        offset=offset, batch_size=batch_size
    )
    task_id = getattr(result, "task_id", None)
    return {"task_id": task_id, "offset": offset, "batch_size": batch_size}


@router.get("/queues")
async def list_queues(
    _admin: User = Depends(require_capability("tasks.manage")),
) -> dict[str, Any]:
    redis = get_redis_client()
    try:
        keys = await redis.keys("taskiq:*")
    except Exception:
        keys = []
    queues: list[dict[str, Any]] = []
    for key in keys:
        try:
            length = await redis.llen(key)
        except Exception:
            length = None
        queues.append({"name": key, "length": length})
    queues.sort(
        key=lambda q: (
            q["length"] is None,
            -(q["length"] or 0),
        )
    )
    return {"items": queues}


@router.get("/lyrics-jobs/{job_id}")
async def get_lyrics_job(
    job_id: str,
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Detail view of a single lyrics job.

    Returns the persistent job row (status, profile, error,
    timings, etc.) merged with the live Redis progress snapshot
    (current stage, percent, recent log lines, terminal state).
    The two sources are intentionally separate: the DB row is
    authoritative once the worker finalises the job, while Redis
    holds the live tail while the task is still running.
    """
    from app.services.lyrics_worker import (
        get_lyrics_progress,
    )

    repo = AdminTasksRepository(session)
    row = await repo.get_lyrics_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")

    progress: dict[str, Any] | None = None
    progress_id = row.progress_id
    if progress_id:
        try:
            progress = await get_lyrics_progress(progress_id)
        except Exception:
            logger.exception(
                "admin_lyrics_progress_read_failed",
                job_id=job_id,
            )
            progress = None

    return {
        "id": row.id,
        "track_id": row.track_id,
        "status": row.status,
        "profile": row.profile,
        "routed_to_worker": row.routed_to_worker,
        "attempts": row.attempts,
        "error": row.error,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "duration_ms": row.duration_ms,
        "created_at": row.created_at,
        "progress_id": progress_id,
        "requested_by_user_id": row.requested_by_user_id,
        "current_tier": row.current_tier,
        "tiers_planned": row.tiers_planned,
        "request_with_sync": row.request_with_sync,
        "request_bypass_cache": row.request_bypass_cache,
        "request_align_existing_text": (
            row.request_align_existing_text
        ),
        "live": progress,
    }


@router.post("/lyrics-jobs/{job_id}/cancel")
async def cancel_lyrics_job(
    job_id: str,
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Cancel a lyrics / compute job (see ``lyrics_job_cancel``)."""
    from app.services.lyrics_job_cancel import (
        cancel_lyrics_job_for_admin,
    )

    out = await cancel_lyrics_job_for_admin(session, job_id)
    if out is None:
        raise HTTPException(status_code=404, detail="job not found")
    return out


@router.post("/lyrics-jobs/cancel-queued")
async def cancel_all_queued_lyrics_jobs(
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Bulk-cancel every lyrics job currently in ``queued`` state.

    Also signals cancel on their progress channels so a worker that
    picks one up right after this call will exit immediately.
    """
    from datetime import UTC, datetime

    from app.services.lyrics_worker import CANCEL_KEY_PREFIX

    queued_rows = await AdminTasksRepository(session).list_queued_lyrics_jobs()

    if not queued_rows:
        return {"cancelled": 0, "items": []}

    redis = get_redis_client()
    now = datetime.now(UTC)
    ids: list[str] = []
    for row in queued_rows:
        if row.progress_id:
            try:
                await redis.set(
                    f"{CANCEL_KEY_PREFIX}{row.progress_id}",
                    "1",
                    ex=600,
                )
            except Exception:
                logger.debug(
                    "admin_bulk_cancel_signal_failed",
                    job_id=row.id,
                )
        row.status = "cancelled"
        row.finished_at = now
        row.error = "cancelled_by_admin_bulk"
        ids.append(row.id)

    await session.commit()
    logger.info(
        "admin_lyrics_bulk_cancel",
        count=len(ids),
    )
    return {"cancelled": len(ids), "items": ids}


@router.get("/lyrics-jobs")
async def list_lyrics_jobs(
    status: str | None = Query(None, max_length=24),
    profile: str | None = Query(None, max_length=32),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows, total = await AdminTasksRepository(session).list_lyrics_jobs(
        status=status,
        profile=profile,
        page=page,
        size=size,
    )
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "id": row.id,
                "track_id": row.track_id,
                "status": row.status,
                "profile": row.profile,
                "routed_to_worker": (row.routed_to_worker),
                "pinned_worker_id": row.pinned_worker_id,
                "queue_priority": row.queue_priority,
                "attempts": row.attempts,
                "error": row.error,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
                "duration_ms": row.duration_ms,
                "created_at": row.created_at,
                "requested_by_user_id": row.requested_by_user_id,
                "current_tier": row.current_tier,
                "tiers_planned": row.tiers_planned,
                "request_with_sync": row.request_with_sync,
                "request_bypass_cache": row.request_bypass_cache,
                "request_align_existing_text": (
                    row.request_align_existing_text
                ),
            }
            for row in rows
        ],
    }


@router.get("/compute-jobs")
async def list_compute_jobs(
    status: str | None = Query(None, max_length=16),
    job_type: str | None = Query(None, max_length=48),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows, total = await AdminTasksRepository(session).list_compute_jobs(
        status=status,
        job_type=job_type,
        page=page,
        size=size,
    )
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "id": row.id,
                "job_type": row.job_type,
                "job_label": _COMPUTE_JOB_LABELS.get(
                    row.job_type,
                    row.job_type,
                ),
                "target_kind": row.target_kind,
                "target_id": row.target_id,
                "status": row.status,
                "priority": row.priority,
                "pinned_worker_id": row.pinned_worker_id,
                "attempts": row.attempts,
                "last_error": row.last_error,
                "claimed_by": row.claimed_by,
                "created_at": row.created_at,
                "finished_at": row.finished_at,
            }
            for row in rows
        ],
    }


@router.get("/worker-audit")
async def list_worker_audit(
    worker_id: str | None = Query(None, max_length=32),
    limit: int = Query(100, ge=1, le=500),
    _admin: User = Depends(require_capability("audio_compute.view_audit")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await AdminTasksRepository(session).list_worker_audit(
        worker_id=worker_id,
        limit=limit,
    )
    return {
        "items": [
            {
                "id": row.id,
                "worker_id": row.worker_id,
                "action": row.action,
                "job_id": row.job_id,
                "status_code": row.status_code,
                "ip": row.ip,
                "meta": row.meta,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


@router.get("/allowed")
async def list_allowed(
    _admin: User = Depends(require_capability("tasks.run")),
) -> dict[str, Any]:
    return {"tasks": sorted(ALLOWED_TASK_NAMES)}


@router.post("/run/{task_name}")
async def run_task(
    task_name: str,
    payload: dict[str, Any] | None = None,
    _admin: User = Depends(require_step_up("tasks.run")),
) -> dict[str, Any]:
    if task_name not in ALLOWED_TASK_NAMES:
        raise HTTPException(
            status_code=400,
            detail="task not in whitelist",
        )
    from app.core.tkq import broker

    args: list[Any] = []
    kwargs: dict[str, Any] = payload or {}
    try:
        task = broker.find_task(task_name)
    except Exception:
        task = None
    if task is None:
        raise HTTPException(
            status_code=404,
            detail="task not registered in broker",
        )
    try:
        result = await task.kiq(*args, **kwargs)
    except Exception as exc:
        logger.exception(
            "admin_task_run_failed",
            task=task_name,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    task_id = getattr(result, "task_id", None) or getattr(result, "id", None)
    return {
        "task_id": task_id,
        "task_name": task_name,
        "queued": True,
    }


class ManualEnqueueRequest(BaseModel):
    task_name: str = Field(min_length=1, max_length=96)
    payload: dict[str, Any] = Field(default_factory=dict)
    queue: str = Field(default="default", max_length=32)
    max_attempts: int = Field(default=3, ge=1, le=10)


@router.post("/manual")
async def manual_enqueue_task(
    body: ManualEnqueueRequest,
    request: Request,
    admin: User = Depends(require_step_up("tasks.run")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Manually enqueue an allowed task with full BackgroundJob tracking.

    Unlike ``POST /run/{task_name}`` (raw ``task.kiq``), this path goes
    through :func:`app.services.background_jobs.enqueue`, so the job is
    visible in ``/tasks/jobs``, attributable via ``created_by_user_id``
    and counted in ``/tasks/types`` aggregations.
    """
    if body.task_name not in ALLOWED_TASK_NAMES:
        raise HTTPException(status_code=400, detail="task not in whitelist")
    from app.core.tkq import broker
    from app.services.background_jobs import (
        IdempotencySkipped,
        TaskPaused,
        enqueue,
    )

    try:
        task = broker.find_task(body.task_name)
    except Exception:
        task = None
    if task is None:
        raise HTTPException(
            status_code=404,
            detail="task not registered in broker",
        )

    try:
        job_id = await enqueue(
            task,
            payload=body.payload,
            queue=body.queue,
            max_attempts=body.max_attempts,
            created_by_user_id=admin.id,
        )
    except TaskPaused as exc:
        raise HTTPException(
            status_code=409,
            detail=f"task type is paused: {exc.task_name}",
        ) from exc
    except IdempotencySkipped as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "admin_manual_enqueue_failed",
            task=body.task_name,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    await AdminActionLogRepository(session).write(
        user_id=admin.id,
        action="tasks.manual.enqueue",
        target_type="task_type",
        target_id=body.task_name[:128],
        ip=(request.client.host if request.client else None),
        meta={
            "job_id": job_id,
            "queue": body.queue,
            "payload_keys": sorted(body.payload.keys())[:32],
        },
    )
    await session.commit()
    return {
        "job_id": job_id,
        "task_name": body.task_name,
        "queue": body.queue,
    }


# ---------------------------------------------------------------------------
# Unified BackgroundJob view (Taskiq-driven jobs kicked through enqueue())
# ---------------------------------------------------------------------------


def _serialize_bgjob(row: BackgroundJob) -> dict[str, Any]:
    progress_id = None
    if isinstance(row.payload, dict):
        raw_progress_id = row.payload.get("progress_id")
        if isinstance(raw_progress_id, str) and raw_progress_id:
            progress_id = raw_progress_id
    return {
        "id": row.id,
        "name": row.name,
        "queue": row.queue,
        "status": row.status,
        "payload": row.payload,
        "attempts": row.attempts,
        "max_attempts": row.max_attempts,
        "scheduled_at": row.scheduled_at,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "duration_ms": row.duration_ms,
        "error": row.error,
        "result_summary": row.result_summary,
        "parent_job_id": row.parent_job_id,
        "scheduled_job_id": row.scheduled_job_id,
        "created_by_user_id": row.created_by_user_id,
        "idempotency_key": row.idempotency_key,
        "taskiq_task_id": row.taskiq_task_id,
        "progress_id": progress_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def _serialize_bgjob_live(row: BackgroundJob) -> dict[str, Any]:
    data = _serialize_bgjob(row)
    progress_id = data.get("progress_id")
    if row.name == _PLAYBACK_REPAIR_TASK_NAME and isinstance(
        progress_id,
        str,
    ):
        from app.services.playback_repair_progress import get_progress

        try:
            data["live"] = await get_progress(progress_id)
        except Exception:
            logger.exception(
                "admin_playback_repair_progress_read_failed",
                job_id=row.id,
                progress_id=progress_id,
            )
            data["live"] = None
    return data


def _bgjob_payload_value(row: BackgroundJob, key: str) -> object | None:
    if not isinstance(row.payload, dict):
        return None
    return row.payload.get(key)


def _bgjob_track_id(row: BackgroundJob) -> int | None:
    raw = _bgjob_payload_value(row, "track_id")
    return raw if isinstance(raw, int) else None


def _bgjob_progress_id(row: BackgroundJob) -> str | None:
    raw = _bgjob_payload_value(row, "progress_id")
    return raw if isinstance(raw, str) and raw else None


def _bgjob_result_status(row: BackgroundJob) -> str | None:
    if not isinstance(row.result_summary, dict):
        return None
    raw = row.result_summary.get("status")
    return raw if isinstance(raw, str) and raw else None


def _bgjob_result_summary(row: BackgroundJob) -> dict[str, Any]:
    return row.result_summary if isinstance(row.result_summary, dict) else {}


def _live_stage(live: dict[str, Any] | None) -> str | None:
    if not live:
        return None
    raw = live.get("stage")
    return raw if isinstance(raw, str) and raw else None


def _live_updated_at(live: dict[str, Any] | None) -> str | None:
    if not live:
        return None
    raw = live.get("updated_at")
    return raw if isinstance(raw, str) and raw else None


def _playback_repair_outcome(row: BackgroundJob) -> str:
    status = _bgjob_result_status(row)
    if status in _PLAYBACK_REPAIR_OUTCOMES:
        return status
    if row.status in {"failed", "failed_terminal"}:
        return "error"
    if row.status == "cancelled":
        return "cancelled"
    return "unknown"


def _inc(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def _string_result_value(
    result: dict[str, Any],
    key: str,
) -> str | None:
    raw = result.get(key)
    return raw if isinstance(raw, str) and raw else None


def _bool_result_value(
    result: dict[str, Any],
    key: str,
) -> bool | None:
    raw = result.get(key)
    return raw if isinstance(raw, bool) else None


def _int_result_value(
    result: dict[str, Any],
    key: str,
) -> int | None:
    raw = result.get(key)
    return raw if isinstance(raw, int) else None


def _dict_result_value(
    result: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    raw = result.get(key)
    return raw if isinstance(raw, dict) else {}


def _playback_repair_diagnostic_item(
    row: BackgroundJob,
    *,
    current_sc_url: str | None,
) -> dict[str, Any]:
    result = _bgjob_result_summary(row)
    refresh = _dict_result_value(result, "refresh_diagnostics")
    return {
        "job_id": row.id,
        "track_id": _bgjob_track_id(row),
        "status": row.status,
        "outcome": _playback_repair_outcome(row),
        "detail": _string_result_value(result, "detail"),
        "http_status": _int_result_value(result, "http_status"),
        "source_platform": _string_result_value(result, "source_platform"),
        "sc_url_before": _string_result_value(result, "sc_url_before"),
        "sc_url_after": (
            _string_result_value(result, "sc_url_after") or current_sc_url
        ),
        "candidate_found": _bool_result_value(refresh, "candidate_found"),
        "candidate_url": _string_result_value(refresh, "candidate_url"),
        "candidate_title": _string_result_value(refresh, "candidate_title"),
        "rejected_reason": _string_result_value(
            refresh,
            "rejected_reason",
        ),
        "conflict_track_id": _int_result_value(refresh, "conflict_track_id"),
        "refresh_error": _string_result_value(refresh, "error"),
    }


async def _purge_bgjob_messages(job_ids: set[str]) -> int:
    if not job_ids:
        return 0
    from app.core.tkq import broker

    redis = get_redis_client()
    keys: list[str] = [broker.queue_name]
    try:
        discovered = await redis.keys(f"{broker.queue_name}:*")
    except Exception:
        discovered = []
    for raw_key in discovered:
        key = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
        if key not in keys:
            keys.append(key)

    removed = 0
    for key in keys:
        try:
            messages = await redis.lrange(key, 0, -1)
        except Exception:
            continue
        for raw in messages:
            try:
                message = broker.formatter.loads(message=raw)
                message.parse_labels()
            except Exception:
                continue
            raw_bgjob_id = message.labels.get("bgjob_id")
            bgjob_id = str(raw_bgjob_id) if raw_bgjob_id else None
            if bgjob_id not in job_ids:
                continue
            try:
                removed += int(await redis.lrem(key, 0, raw) or 0)
            except Exception:
                logger.debug(
                    "admin_bgjob_queue_message_purge_failed",
                    job_id=bgjob_id,
                    queue=key,
                )
    return removed


def _serialize_schedule(row: ScheduledJob) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "task_name": row.task_name,
        "queue": row.queue,
        "cron": row.cron,
        "payload": row.payload,
        "enabled": row.enabled,
        "last_run_at": row.last_run_at,
        "next_run_at": row.next_run_at,
        "last_status": row.last_status,
        "last_error": row.last_error,
        "last_job_id": row.last_job_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("/overview")
async def tasks_overview(
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Single-pane summary: queues + bgjob status counts + due schedules."""
    redis = get_redis_client()
    queues: list[dict[str, Any]] = []
    try:
        keys = await redis.keys("taskiq:*")
        for key in keys:
            try:
                length = await redis.llen(key)
            except Exception:
                length = None
            queues.append({"name": key, "length": length})
        queues.sort(
            key=lambda q: (
                q["length"] is None,
                -(q["length"] or 0),
            )
        )
    except Exception:
        pass

    repo = AdminTasksRepository(session)
    bgjob_counts = await repo.count_background_jobs_by_status()
    compute_counts = await repo.count_compute_jobs_by_status()
    lyrics_counts = await repo.count_lyrics_jobs_by_status()
    upcoming_rows = await repo.list_upcoming_schedules(limit=20)

    return {
        "queues": queues,
        "background_jobs": bgjob_counts,
        "compute_jobs": compute_counts,
        "lyrics_jobs": lyrics_counts,
        "upcoming_schedules": [_serialize_schedule(r) for r in upcoming_rows],
    }


@router.post("/playback-repair/summary")
async def playback_repair_summary(
    body: PlaybackRepairSummaryRequest,
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    job_ids = [
        job_id
        for job_id in dict.fromkeys(body.job_ids)
        if isinstance(job_id, str) and job_id
    ]
    if len(job_ids) > _PLAYBACK_REPAIR_SUMMARY_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=(
                "too many job ids; " f"max {_PLAYBACK_REPAIR_SUMMARY_LIMIT}"
            ),
        )
    rows = [
        row
        for row in await AdminTasksRepository(
            session,
        ).list_background_jobs_by_ids(job_ids)
        if row.name == _PLAYBACK_REPAIR_TASK_NAME
    ]
    track_ids = [
        track_id
        for track_id in (_bgjob_track_id(row) for row in rows)
        if track_id is not None
    ]
    current_sc_urls: dict[int, str | None] = {}
    if track_ids:
        track_rows = await session.execute(
            select(Track.id, Track.sc_url).where(Track.id.in_(track_ids))
        )
        current_sc_urls = {
            int(track_id): sc_url for track_id, sc_url in track_rows.all()
        }
    progress_by_job: dict[str, str] = {}
    for row in rows:
        progress_id = _bgjob_progress_id(row)
        if progress_id:
            progress_by_job[row.id] = progress_id

    live_by_progress: dict[str, dict[str, Any]] = {}
    if progress_by_job:
        from app.services.playback_repair_progress import get_many_progress

        try:
            live_by_progress = await get_many_progress(
                list(progress_by_job.values()),
            )
        except Exception:
            logger.exception("admin_playback_repair_summary_progress_failed")
            live_by_progress = {}

    statuses: dict[str, int] = {}
    outcomes: dict[str, int] = {
        "repaired": 0,
        "unresolved": 0,
        "skipped": 0,
        "not_found": 0,
        "error": 0,
        "cancelled": 0,
        "unknown": 0,
    }
    stages: dict[str, int] = {}
    current: dict[str, Any] | None = None
    items: list[dict[str, Any]] = []
    unresolved_items: list[dict[str, Any]] = []
    retryable_track_ids: list[int] = []
    processed = 0

    for row in rows:
        _inc(statuses, row.status)
        progress_id = progress_by_job.get(row.id)
        live = (
            live_by_progress.get(progress_id)
            if progress_id is not None
            else None
        )
        stage = _live_stage(live)
        result_status = _bgjob_result_status(row)
        if not stage and result_status:
            stage = result_status
        if not stage and row.status in _ACTIVE_BACKGROUND_JOB_STATUSES:
            stage = row.status
        if stage:
            _inc(stages, stage)

        is_terminal = row.status in _TERMINAL_BACKGROUND_JOB_STATUSES
        if result_status in _PLAYBACK_REPAIR_OUTCOMES:
            is_terminal = True
        if live and live.get("state") == "finished":
            is_terminal = True
        if is_terminal:
            processed += 1
            outcome = _playback_repair_outcome(row)
            _inc(outcomes, outcome)
            if outcome == "unresolved":
                track_id = _bgjob_track_id(row)
                if track_id is not None:
                    retryable_track_ids.append(track_id)
                unresolved_items.append(
                    _playback_repair_diagnostic_item(
                        row,
                        current_sc_url=(
                            current_sc_urls.get(track_id)
                            if track_id is not None
                            else None
                        ),
                    )
                )

        item = {
            "job_id": row.id,
            "track_id": _bgjob_track_id(row),
            "status": row.status,
            "progress_id": progress_id,
            "stage": stage,
            "updated_at": _live_updated_at(live),
        }
        if row.status in _ACTIVE_BACKGROUND_JOB_STATUSES:
            items.append(item)
            if current is None or (
                row.status == "running" and current.get("status") != "running"
            ):
                current = item

    matched = len(rows)
    return {
        "requested": len(job_ids),
        "matched": matched,
        "processed": processed,
        "remaining": max(0, matched - processed),
        "statuses": statuses,
        "outcomes": outcomes,
        "stages": stages,
        "current": current,
        "items": items[:20],
        "unresolved_items": unresolved_items[:500],
        "retryable_track_ids": list(dict.fromkeys(retryable_track_ids)),
    }


@router.post("/playback-repair/retry-unresolved")
async def retry_unresolved_playback_repairs(
    body: PlaybackRepairRetryUnresolvedRequest,
    admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    job_ids = [
        job_id
        for job_id in dict.fromkeys(body.job_ids)
        if isinstance(job_id, str) and job_id
    ]
    if len(job_ids) > _PLAYBACK_REPAIR_SUMMARY_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=(
                "too many job ids; " f"max {_PLAYBACK_REPAIR_SUMMARY_LIMIT}"
            ),
        )
    rows = [
        row
        for row in await AdminTasksRepository(
            session,
        ).list_background_jobs_by_ids(job_ids)
        if (
            row.name == _PLAYBACK_REPAIR_TASK_NAME
            and _bgjob_result_status(row) == "unresolved"
        )
    ]
    track_ids = [
        track_id
        for track_id in (_bgjob_track_id(row) for row in rows)
        if track_id is not None
    ]
    if not track_ids:
        return {
            "requested": 0,
            "queued": 0,
            "skipped": 0,
            "missing": 0,
            "job_ids": [],
            "progress_ids": [],
            "detail": "No unresolved playback repair jobs to retry",
        }

    from app.services.admin_service import AdminService

    result = await AdminService(session).enqueue_tracks_playback_repair(
        list(dict.fromkeys(track_ids)),
        actor_id=admin.id,
        force_requeue=True,
    )
    return result.model_dump()


@router.get("/jobs")
async def list_background_jobs(
    name: str | None = Query(None, max_length=96),
    queue: str | None = Query(None, max_length=32),
    status: str | None = Query(None, max_length=24),
    scheduled_job_id: str | None = Query(None, max_length=64),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows, total = await AdminTasksRepository(session).list_background_jobs(
        name=name,
        queue=queue,
        status=status,
        scheduled_job_id=scheduled_job_id,
        page=page,
        size=size,
    )
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [_serialize_bgjob(r) for r in rows],
    }


@router.get("/jobs/active")
async def list_active_background_jobs(
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await AdminTasksRepository(session).list_active_background_jobs(
        limit=20,
    )
    return {
        "total": len(rows),
        "items": [await _serialize_bgjob_live(row) for row in rows],
    }


@router.post("/jobs/cancel-active")
async def cancel_active_background_jobs(
    request: Request,
    body: BackgroundJobBulkCancelRequest | None = Body(default=None),
    admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> BackgroundJobBulkCancelResponse:
    from datetime import UTC, datetime

    spec = body or BackgroundJobBulkCancelRequest()
    if spec.status and spec.status not in _ACTIVE_BACKGROUND_JOB_STATUSES:
        return BackgroundJobBulkCancelResponse(
            matched=0,
            cancelled=0,
            cancelling=0,
            purged_messages=0,
            items=[],
        )
    rows = await AdminTasksRepository(
        session,
    ).list_cancellable_background_jobs(
        name=spec.name,
        queue=spec.queue,
        status=spec.status,
        scheduled_job_id=spec.scheduled_job_id,
    )
    if not rows:
        return BackgroundJobBulkCancelResponse(
            matched=0,
            cancelled=0,
            cancelling=0,
            purged_messages=0,
            items=[],
        )

    now = datetime.now(UTC)
    ids: list[str] = []
    queued_ids: set[str] = set()
    cancelled = 0
    cancelling = 0
    for row in rows:
        ids.append(row.id)
        if row.status == "queued":
            queued_ids.add(row.id)
            row.status = "cancelled"
            row.finished_at = now
            row.error = "cancelled_by_admin_bulk"
            cancelled += 1
        else:
            row.status = "cancelling"
            row.error = "cancel_requested_by_admin_bulk"
            cancelling += 1

    await session.commit()
    purged_messages = await _purge_bgjob_messages(queued_ids)
    for job_id in ids:
        await signal_cancel(job_id)
    await AdminActionLogRepository(session).write(
        user_id=admin.id,
        action="tasks.background_jobs.cancel_active",
        target_type="background_job",
        target_id="bulk",
        ip=(request.client.host if request.client else None),
        meta={
            "filters": spec.model_dump(exclude_none=True),
            "matched": len(ids),
            "cancelled": cancelled,
            "cancelling": cancelling,
            "purged_messages": purged_messages,
            "items_sample": ids[:100],
            "items_truncated": len(ids) > 100,
        },
    )
    await session.commit()

    logger.info(
        "admin_background_jobs_bulk_cancel",
        matched=len(ids),
        cancelled=cancelled,
        cancelling=cancelling,
        purged_messages=purged_messages,
    )
    return BackgroundJobBulkCancelResponse(
        matched=len(ids),
        cancelled=cancelled,
        cancelling=cancelling,
        purged_messages=purged_messages,
        items=ids,
    )


@router.get("/jobs/{job_id}")
async def get_background_job(
    job_id: str,
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await AdminTasksRepository(session).get_background_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return await _serialize_bgjob_live(row)


@router.post("/jobs/{job_id}/cancel")
async def cancel_background_job(
    job_id: str,
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await AdminTasksRepository(session).get_background_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    if row.status in ("done", "failed_terminal", "cancelled"):
        return _serialize_bgjob(row)
    row.status = "cancelling"
    await session.commit()
    await signal_cancel(job_id)
    return _serialize_bgjob(row)


@router.post("/jobs/{job_id}/retry")
async def retry_background_job(
    job_id: str,
    _admin: User = Depends(require_step_up("tasks.run")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Re-enqueue a failed/cancelled job with a fresh row."""
    from app.services.background_jobs import (
        IdempotencySkipped,
        enqueue,
    )

    row = await AdminTasksRepository(session).get_background_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    from app.core.tkq import broker as _broker

    task = _broker.find_task(row.name)
    if task is None:
        raise HTTPException(
            status_code=400,
            detail=f"task not registered: {row.name}",
        )
    try:
        new_id = await enqueue(
            task,
            payload=row.payload or {},
            queue=row.queue or "default",
            max_attempts=row.max_attempts or 3,
            parent_job_id=row.id,
            job_id_payload_key=(
                "background_job_id"
                if row.name == _PLAYBACK_REPAIR_TASK_NAME
                else None
            ),
        )
    except IdempotencySkipped as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"new_job_id": new_id, "parent_job_id": row.id}


# ---------------------------------------------------------------------------
# Schedules CRUD
# ---------------------------------------------------------------------------


def _validate_cron(expr: str) -> None:
    from croniter import croniter as _cron

    if not _cron.is_valid(expr):
        raise HTTPException(
            status_code=400,
            detail=f"invalid cron expression: {expr}",
        )


@router.get("/schedules")
async def list_schedules(
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await AdminTasksRepository(session).list_all_schedules()
    return {"items": [_serialize_schedule(r) for r in rows]}


@router.post("/schedules")
async def create_schedule(
    body: dict[str, Any],
    _admin: User = Depends(require_step_up("tasks.run")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    import uuid as _uuid

    name = (body.get("name") or "").strip()
    task_name = (body.get("task_name") or "").strip()
    cron = (body.get("cron") or "").strip()
    if not name or not task_name or not cron:
        raise HTTPException(
            status_code=400,
            detail="name, task_name, cron are required",
        )
    _validate_cron(cron)

    repo = AdminTasksRepository(session)
    existing = await repo.find_schedule_by_name(name)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"schedule '{name}' already exists",
        )

    row = ScheduledJob(
        id=_uuid.uuid4().hex,
        name=name,
        task_name=task_name,
        queue=body.get("queue") or "default",
        cron=cron,
        payload=body.get("payload") or None,
        enabled=bool(body.get("enabled", True)),
    )
    await repo.add(row)
    await session.commit()
    return _serialize_schedule(row)


@router.patch("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    body: dict[str, Any],
    _admin: User = Depends(require_step_up("tasks.run")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await AdminTasksRepository(session).get_schedule(schedule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="schedule not found")

    if "cron" in body:
        cron = (body.get("cron") or "").strip()
        _validate_cron(cron)
        row.cron = cron
        row.next_run_at = None  # recompute on next tick
    if "task_name" in body and body["task_name"]:
        row.task_name = str(body["task_name"]).strip()
    if "queue" in body and body["queue"]:
        row.queue = str(body["queue"]).strip()
    if "payload" in body:
        row.payload = body["payload"]
    if "enabled" in body:
        row.enabled = bool(body["enabled"])

    await session.commit()
    return _serialize_schedule(row)


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    _admin: User = Depends(require_step_up("tasks.run")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await AdminTasksRepository(session).get_schedule(schedule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="schedule not found")
    await AdminTasksRepository(session).delete(row)
    await session.commit()
    return {"deleted": schedule_id}


@router.post("/schedules/{schedule_id}/run-now")
async def run_schedule_now(
    schedule_id: str,
    _admin: User = Depends(require_step_up("tasks.run")),
) -> dict[str, Any]:
    from app.services.scheduler_service import run_now

    job_id = await run_now(schedule_id)
    if job_id is None:
        raise HTTPException(
            status_code=400,
            detail=("schedule not found or task not registered"),
        )
    return {"job_id": job_id, "schedule_id": schedule_id}


# ---------------------------------------------------------------------------
# Dispatcher panel: per-type metrics, pause/resume, workers, audit, purge
# ---------------------------------------------------------------------------


_PURGEABLE_BG_STATUSES: frozenset[str] = frozenset(
    {"done", "failed", "failed_terminal", "cancelled"},
)


@router.get("/types")
async def list_task_types(
    period_hours: int = Query(24, ge=1, le=720),
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Per-task-name aggregate for the dispatcher panel.

    Walks ``background_jobs`` (Taskiq layer) and ``compute_jobs``
    (worker layer) and folds them into a single ``items`` list grouped
    by task name. Pause flags are returned so the UI can render the
    toggle in one round-trip.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func as sa_func

    from app.models.compute_job import ComputeJob
    from app.services.task_pause_service import list_paused_tasks

    hours = max(1, min(720, int(period_hours)))
    start = datetime.now(UTC) - timedelta(hours=hours)

    bg_rows = (
        await session.execute(
            select(
                BackgroundJob.name,
                BackgroundJob.status,
                sa_func.count(BackgroundJob.id),
            ).group_by(BackgroundJob.name, BackgroundJob.status)
        )
    ).all()

    bg_perf = (
        await session.execute(
            select(
                BackgroundJob.name,
                sa_func.count(BackgroundJob.id),
                sa_func.avg(BackgroundJob.duration_ms),
                sa_func.max(BackgroundJob.duration_ms),
            )
            .where(
                BackgroundJob.status == "done",
                BackgroundJob.finished_at >= start,
            )
            .group_by(BackgroundJob.name)
        )
    ).all()

    bg_failed_period = (
        await session.execute(
            select(
                BackgroundJob.name,
                sa_func.count(BackgroundJob.id),
            )
            .where(
                BackgroundJob.status.in_(("failed", "failed_terminal")),
                BackgroundJob.finished_at >= start,
            )
            .group_by(BackgroundJob.name)
        )
    ).all()

    compute_rows = (
        await session.execute(
            select(
                ComputeJob.job_type,
                ComputeJob.status,
                sa_func.count(ComputeJob.id),
            ).group_by(ComputeJob.job_type, ComputeJob.status)
        )
    ).all()

    paused = await list_paused_tasks()

    schedule_rows = (
        await session.execute(
            select(
                ScheduledJob.task_name,
                ScheduledJob.id,
                ScheduledJob.name,
                ScheduledJob.cron,
                ScheduledJob.enabled,
                ScheduledJob.next_run_at,
            )
        )
    ).all()
    schedules_by_task: dict[str, list[dict[str, Any]]] = {}
    for tn, sid, sname, cron, enabled, next_run in schedule_rows:
        schedules_by_task.setdefault(str(tn), []).append(
            {
                "id": sid,
                "name": sname,
                "cron": cron,
                "enabled": bool(enabled),
                "next_run_at": (next_run.isoformat() if next_run else None),
            }
        )

    items: dict[str, dict[str, Any]] = {}

    def _ensure(name: str, kind: str) -> dict[str, Any]:
        bucket = items.setdefault(
            name,
            {
                "name": name,
                "kind": kind,
                "paused": False,
                "paused_meta": None,
                "by_status": {},
                "done_period": 0,
                "failed_period": 0,
                "avg_duration_ms": None,
                "max_duration_ms": None,
                "schedules": [],
            },
        )
        if bucket["kind"] != kind:
            bucket["kind"] = "mixed"
        return bucket

    for name, status, count in bg_rows:
        bucket = _ensure(str(name), "taskiq")
        bucket["by_status"][str(status)] = int(count or 0)

    for name, count, avg_ms, max_ms in bg_perf:
        bucket = _ensure(str(name), "taskiq")
        bucket["done_period"] = int(count or 0)
        bucket["avg_duration_ms"] = (
            int(round(float(avg_ms))) if avg_ms is not None else None
        )
        bucket["max_duration_ms"] = int(max_ms) if max_ms is not None else None

    for name, count in bg_failed_period:
        bucket = _ensure(str(name), "taskiq")
        bucket["failed_period"] = int(count or 0)

    for job_type, status, count in compute_rows:
        bucket = _ensure(str(job_type), "compute")
        bucket["by_status"][str(status)] = bucket["by_status"].get(
            str(status), 0
        ) + int(count or 0)

    for name, meta in paused.items():
        bucket = _ensure(name, "taskiq")
        bucket["paused"] = True
        bucket["paused_meta"] = meta

    for task_name_key, schedules in schedules_by_task.items():
        bucket = _ensure(task_name_key, "taskiq")
        bucket["schedules"] = schedules

    sorted_items = sorted(
        items.values(),
        key=lambda b: (
            -sum(b["by_status"].values()),
            b["name"],
        ),
    )
    return {
        "period_hours": hours,
        "paused": paused,
        "items": sorted_items,
    }


class TaskPauseRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=200)
    drain: bool = Field(
        default=False,
        description=(
            "If true, also cancel queued/running jobs of this type "
            "after setting the pause flag (hard pause / drain)."
        ),
    )


@router.get("/types/{task_name}/affected")
async def task_affected_preview(
    task_name: str,
    _admin: User = Depends(require_capability("tasks.manage")),
) -> dict[str, int]:
    """How many jobs would be cancelled by a drain right now."""
    from app.services.task_pause_service import affected_jobs_preview

    return await affected_jobs_preview(task_name)


@router.get("/types/{task_name}/timeseries")
async def task_timeseries(
    task_name: str,
    period_hours: int = Query(6, ge=1, le=168),
    bucket_minutes: int = Query(5, ge=1, le=60),
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Per-task time series for the dispatcher panel charts.

    Returns one bucket per ``bucket_minutes`` for the trailing
    ``period_hours``, plus per-period p95 / avg / max durations. Used
    by the UI to render sparklines (throughput) and the latency
    summary card. Empty buckets are present with ``0`` so the front
    end can render contiguous x-axis without gap-handling logic.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func as sa_func
    from sqlalchemy import literal_column

    hours = max(1, min(168, int(period_hours)))
    bucket_s = max(1, min(60, int(bucket_minutes))) * 60
    now = datetime.now(UTC)
    start = now - timedelta(hours=hours)
    bucket_count = max(1, (hours * 3600) // bucket_s)

    created_rows = (
        await session.execute(
            select(
                sa_func.floor(
                    sa_func.extract("epoch", BackgroundJob.created_at)
                    / bucket_s
                ).label("bucket"),
                sa_func.count(BackgroundJob.id),
            )
            .where(
                BackgroundJob.name == task_name,
                BackgroundJob.created_at >= start,
            )
            .group_by(literal_column("bucket"))
        )
    ).all()

    succeeded_rows = (
        await session.execute(
            select(
                sa_func.floor(
                    sa_func.extract("epoch", BackgroundJob.finished_at)
                    / bucket_s
                ).label("bucket"),
                sa_func.count(BackgroundJob.id),
            )
            .where(
                BackgroundJob.name == task_name,
                BackgroundJob.finished_at >= start,
                BackgroundJob.status == "done",
            )
            .group_by(literal_column("bucket"))
        )
    ).all()

    failed_rows = (
        await session.execute(
            select(
                sa_func.floor(
                    sa_func.extract("epoch", BackgroundJob.finished_at)
                    / bucket_s
                ).label("bucket"),
                sa_func.count(BackgroundJob.id),
            )
            .where(
                BackgroundJob.name == task_name,
                BackgroundJob.finished_at >= start,
                BackgroundJob.status.in_(("failed", "failed_terminal")),
            )
            .group_by(literal_column("bucket"))
        )
    ).all()

    created_map = {int(b): int(c or 0) for b, c in created_rows}
    succeeded_map = {int(b): int(c or 0) for b, c in succeeded_rows}
    failed_map = {int(b): int(c or 0) for b, c in failed_rows}

    end_bucket = int(now.timestamp() // bucket_s)
    buckets: list[dict[str, Any]] = []
    for i in range(bucket_count):
        b = end_bucket - (bucket_count - 1 - i)
        ts = b * bucket_s
        buckets.append(
            {
                "ts": ts,
                "created": created_map.get(b, 0),
                "succeeded": succeeded_map.get(b, 0),
                "failed": failed_map.get(b, 0),
            }
        )

    perf_row = (
        await session.execute(
            select(
                sa_func.percentile_disc(0.95)
                .within_group(BackgroundJob.duration_ms.asc())
                .label("p95"),
                sa_func.avg(BackgroundJob.duration_ms),
                sa_func.max(BackgroundJob.duration_ms),
                sa_func.count(BackgroundJob.id),
            ).where(
                BackgroundJob.name == task_name,
                BackgroundJob.status == "done",
                BackgroundJob.finished_at >= start,
            )
        )
    ).first()
    if perf_row is not None:
        p95, avg_ms, max_ms, n = perf_row
    else:
        p95 = avg_ms = max_ms = n = None

    return {
        "task_name": task_name,
        "period_hours": hours,
        "bucket_seconds": bucket_s,
        "buckets": buckets,
        "p95_duration_ms": (int(p95) if p95 is not None else None),
        "avg_duration_ms": (
            int(round(float(avg_ms))) if avg_ms is not None else None
        ),
        "max_duration_ms": (int(max_ms) if max_ms is not None else None),
        "samples": int(n or 0),
    }


@router.post("/types/{task_name}/pause")
async def pause_task_endpoint(
    task_name: str,
    request: Request,
    body: TaskPauseRequest = Body(default_factory=TaskPauseRequest),
    admin: User = Depends(require_step_up("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.services.task_pause_service import drain_task, pause_task

    meta = await pause_task(
        task_name,
        by_admin_id=admin.id,
        reason=body.reason,
    )
    drained: dict[str, int] | None = None
    if body.drain:
        drained = await drain_task(task_name)
    await AdminActionLogRepository(session).write(
        user_id=admin.id,
        action=(
            "tasks.types.pause_drain" if body.drain else "tasks.types.pause"
        ),
        target_type="task_type",
        target_id=task_name[:128],
        ip=(request.client.host if request.client else None),
        meta={
            "reason": body.reason,
            "drained": drained,
        },
    )
    await session.commit()
    return {
        "task_name": task_name,
        "paused": True,
        "meta": meta,
        "drained": drained,
    }


@router.post("/types/{task_name}/resume")
async def resume_task_endpoint(
    task_name: str,
    request: Request,
    admin: User = Depends(require_step_up("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.services.task_pause_service import resume_task

    removed = await resume_task(task_name)
    await AdminActionLogRepository(session).write(
        user_id=admin.id,
        action="tasks.types.resume",
        target_type="task_type",
        target_id=task_name[:128],
        ip=(request.client.host if request.client else None),
        meta=None,
    )
    await session.commit()
    return {
        "task_name": task_name,
        "paused": False,
        "removed": removed,
    }


@router.get("/workers")
async def list_workers(
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Compute workers with live concurrency + Taskiq leader presence.

    Per-worker fields added on top of the bare ``compute_workers`` row:

    * ``current_claims`` — count of ``compute_jobs`` currently claimed
      by this worker (status ``claimed``).
    * ``recent_throughput_5m`` — successful jobs finished in the last
      5 minutes (status ``succeeded``).
    * ``anomaly_flags_in_window`` — current value of the Redis counter
      from :mod:`app.services.compute_anomaly_service`; non-zero means
      the worker is on the auto-suspend path.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func as sa_func

    from app.models.compute_job import ComputeJob
    from app.models.compute_worker import ComputeWorker

    rows = (
        (
            await session.execute(
                select(ComputeWorker).order_by(
                    ComputeWorker.last_seen_at.desc().nullslast(),
                    ComputeWorker.id,
                )
            )
        )
        .scalars()
        .all()
    )

    claims_rows = (
        await session.execute(
            select(
                ComputeJob.claimed_by,
                sa_func.count(ComputeJob.id),
            )
            .where(
                ComputeJob.status == "claimed",
                ComputeJob.claimed_by.is_not(None),
            )
            .group_by(ComputeJob.claimed_by)
        )
    ).all()
    claims_map = {str(w): int(c or 0) for w, c in claims_rows}

    recent_cut = datetime.now(UTC) - timedelta(minutes=5)
    throughput_rows = (
        await session.execute(
            select(
                ComputeJob.claimed_by,
                sa_func.count(ComputeJob.id),
            )
            .where(
                ComputeJob.status == "succeeded",
                ComputeJob.finished_at >= recent_cut,
                ComputeJob.claimed_by.is_not(None),
            )
            .group_by(ComputeJob.claimed_by)
        )
    ).all()
    throughput_map = {str(w): int(c or 0) for w, c in throughput_rows}

    redis_client = None
    with contextlib.suppress(Exception):
        redis_client = get_redis_client()

    anomaly_map: dict[str, int] = {}
    if redis_client is not None:
        try:
            from app.services.compute_anomaly_service import (
                FLAG_KEY_PREFIX,
            )

            pipe = redis_client.pipeline(transaction=False)
            ids = [w.id for w in rows]
            for wid in ids:
                pipe.get(f"{FLAG_KEY_PREFIX}{wid}")
            res = await pipe.execute()
            for wid, raw in zip(ids, res, strict=False):
                try:
                    anomaly_map[wid] = int(raw) if raw else 0
                except (TypeError, ValueError):
                    anomaly_map[wid] = 0
        except Exception:
            logger.warning("admin_workers_anomaly_lookup_failed")

    workers: list[dict[str, Any]] = []
    for w in rows:
        workers.append(
            {
                "id": w.id,
                "name": w.name,
                "profile": w.profile,
                "active": w.active,
                "max_concurrent_jobs": w.max_concurrent_jobs,
                "last_seen_at": w.last_seen_at,
                "last_ip": w.last_ip,
                "revoked_at": w.revoked_at,
                "suspended_until": w.suspended_until,
                "suspended_reason": w.suspended_reason,
                "claims_paused_until": w.claims_paused_until,
                "claims_pause_reason": w.claims_pause_reason,
                "worker_package_version": (w.worker_package_version),
                "current_claims": claims_map.get(w.id, 0),
                "recent_throughput_5m": throughput_map.get(w.id, 0),
                "anomaly_flags_in_window": anomaly_map.get(w.id, 0),
            }
        )

    leader_owner: str | None = None
    leader_ttl: int | None = None
    if redis_client is not None:
        try:
            raw = await redis_client.get("bgjob:scheduler:leader")
            if raw is not None:
                leader_owner = (
                    raw.decode() if isinstance(raw, bytes) else str(raw)
                )
                ttl = await redis_client.ttl("bgjob:scheduler:leader")
                leader_ttl = int(ttl) if ttl is not None else None
        except Exception:
            logger.warning("admin_workers_leader_lookup_failed")

    return {
        "workers": workers,
        "scheduler_leader": {
            "owner": leader_owner,
            "ttl_seconds": leader_ttl,
        },
    }


@router.get("/audit")
async def list_audit(
    page: int = Query(1, ge=1, le=1000),
    size: int = Query(50, ge=1, le=200),
    action_prefix: str = Query(
        "tasks.",
        max_length=64,
        description=(
            "Prefix for the action column. Defaults to 'tasks.' so the "
            "panel only shows task-related admin actions."
        ),
    ),
    user_id: int | None = Query(None, ge=1),
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repo = AdminActionLogRepository(session)
    rows, total = await repo.list_paginated(
        page=page,
        size=size,
        action_prefix=action_prefix or None,
        user_id=user_id,
    )
    items = [
        {
            "id": int(r.id),
            "user_id": int(r.user_id),
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "ip": r.ip,
            "meta": r.meta,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
    }


class BackgroundJobsPurgeRequest(BaseModel):
    older_than_hours: int = Field(default=24, ge=1, le=24 * 90)
    statuses: list[str] = Field(
        default_factory=lambda: [
            "done",
            "failed",
            "failed_terminal",
            "cancelled",
        ],
    )
    name: str | None = Field(default=None, max_length=96)


class BackgroundJobsPurgeResponse(BaseModel):
    deleted: int
    older_than_hours: int
    statuses: list[str]


@router.post(
    "/jobs/purge",
    response_model=BackgroundJobsPurgeResponse,
)
async def purge_background_jobs(
    body: BackgroundJobsPurgeRequest,
    request: Request,
    admin: User = Depends(require_step_up("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> BackgroundJobsPurgeResponse:
    """Hard-delete terminal ``background_jobs`` rows older than cutoff.

    Refuses to touch active statuses (``queued``/``running``/
    ``cancelling``) — those go through ``cancel-active`` first.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete as sa_delete

    statuses = [s for s in body.statuses if s in _PURGEABLE_BG_STATUSES]
    if not statuses:
        raise HTTPException(
            status_code=400,
            detail="no terminal statuses selected",
        )

    cutoff = datetime.now(UTC) - timedelta(hours=body.older_than_hours)
    stmt = sa_delete(BackgroundJob).where(
        BackgroundJob.status.in_(statuses),
        BackgroundJob.created_at < cutoff,
    )
    if body.name:
        stmt = stmt.where(BackgroundJob.name == body.name)
    result = await session.execute(stmt)
    await session.commit()
    deleted = int(result.rowcount or 0)

    await AdminActionLogRepository(session).write(
        user_id=admin.id,
        action="tasks.background_jobs.purge",
        target_type="background_job",
        target_id="bulk",
        ip=(request.client.host if request.client else None),
        meta={
            "older_than_hours": body.older_than_hours,
            "statuses": statuses,
            "name": body.name,
            "deleted": deleted,
        },
    )
    await session.commit()
    return BackgroundJobsPurgeResponse(
        deleted=deleted,
        older_than_hours=body.older_than_hours,
        statuses=statuses,
    )


class ComputeJobsPurgeRequest(BaseModel):
    older_than_hours: int = Field(default=24, ge=1, le=24 * 30)
    status: str = Field(default="pending", max_length=16)


class ComputeJobsPurgeResponse(BaseModel):
    deleted: int
    older_than_hours: int
    status: str
    remaining: int


@router.post(
    "/compute-jobs/purge",
    response_model=ComputeJobsPurgeResponse,
)
async def purge_compute_jobs_endpoint(
    body: ComputeJobsPurgeRequest,
    request: Request,
    admin: User = Depends(require_step_up("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> ComputeJobsPurgeResponse:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete as sa_delete
    from sqlalchemy import func as sa_func

    from app.models.compute_job import ComputeJob

    if body.status not in {"pending", "failed", "succeeded"}:
        raise HTTPException(
            status_code=400,
            detail="status must be one of pending|failed|succeeded",
        )
    cutoff = datetime.now(UTC) - timedelta(hours=body.older_than_hours)
    result = await session.execute(
        sa_delete(ComputeJob).where(
            ComputeJob.status == body.status,
            ComputeJob.created_at < cutoff,
        )
    )
    await session.commit()
    deleted = int(result.rowcount or 0)
    remaining_row = await session.execute(
        select(sa_func.count(ComputeJob.id)).where(
            ComputeJob.status == body.status
        )
    )
    remaining = int(remaining_row.scalar_one() or 0)

    await AdminActionLogRepository(session).write(
        user_id=admin.id,
        action="tasks.compute_jobs.purge",
        target_type="compute_job",
        target_id="bulk",
        ip=(request.client.host if request.client else None),
        meta={
            "older_than_hours": body.older_than_hours,
            "status": body.status,
            "deleted": deleted,
        },
    )
    await session.commit()
    return ComputeJobsPurgeResponse(
        deleted=deleted,
        older_than_hours=body.older_than_hours,
        status=body.status,
        remaining=remaining,
    )
