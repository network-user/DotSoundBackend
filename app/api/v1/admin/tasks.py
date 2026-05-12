"""Admin task-management endpoints (Taskiq + lyrics_jobs)."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.dependencies import (
    get_db,
    require_capability,
    require_step_up,
)
from app.models.background_job import BackgroundJob
from app.models.scheduled_job import ScheduledJob
from app.models.user import User
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
        "lyrics_discovery_sweep_task",
        "generate_and_upload_cover",
        "admin.alert.send",
        "normalize_track_titles_batch",
    }
)


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


# ---------------------------------------------------------------------------
# Unified BackgroundJob view (Taskiq-driven jobs kicked through enqueue())
# ---------------------------------------------------------------------------


def _serialize_bgjob(row: BackgroundJob) -> dict[str, Any]:
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
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


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


@router.get("/jobs")
async def list_background_jobs(
    name: str | None = Query(None, max_length=96),
    queue: str | None = Query(None, max_length=32),
    status: str | None = Query(None, max_length=24),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows, total = await AdminTasksRepository(session).list_background_jobs(
        name=name,
        queue=queue,
        status=status,
        page=page,
        size=size,
    )
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [_serialize_bgjob(r) for r in rows],
    }


@router.get("/jobs/{job_id}")
async def get_background_job(
    job_id: str,
    _admin: User = Depends(require_capability("tasks.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await AdminTasksRepository(session).get_background_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _serialize_bgjob(row)


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
