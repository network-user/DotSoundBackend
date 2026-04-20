"""Admin task-management endpoints (Taskiq + lyrics_jobs)."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.dependencies import (
    get_db,
    require_capability,
    require_step_up,
)
from app.models.lyrics_job import LyricsJob
from app.models.user import User
from app.models.worker_audit import WorkerAuditLog

router = APIRouter(prefix="/tasks", tags=["admin-tasks"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

ALLOWED_TASK_NAMES: frozenset[str] = frozenset(
    {
        "transcode_and_upload",
        "transcode_hls_only",
        "refresh_tor_list",
        "transcode_video",
        "generate_lyrics_task",
        "generate_and_upload_cover",
        "admin.alert.send",
    }
)


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


_TERMINAL_LYRICS_STATUSES: frozenset[str] = frozenset(
    {"done", "error", "cancelled", "not_found"}
)


@router.get("/lyrics-jobs/{job_id}")
async def get_lyrics_job(
    job_id: str,
    _admin: User = Depends(
        require_capability("tasks.manage")
    ),
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

    row = (
        await session.execute(
            select(LyricsJob).where(LyricsJob.id == job_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404, detail="job not found"
        )

    progress: dict[str, Any] | None = None
    progress_id = row.progress_id
    if progress_id:
        try:
            progress = await get_lyrics_progress(
                progress_id
            )
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
        "live": progress,
    }


@router.post("/lyrics-jobs/{job_id}/cancel")
async def cancel_lyrics_job(
    job_id: str,
    _admin: User = Depends(
        require_capability("tasks.manage")
    ),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Cancel a lyrics job.

    For a currently-running job the CANCEL flag is set on the
    progress channel; the worker picks it up between stages and
    exits at the next safe boundary. For a job still in ``queued``
    state (worker never picked it up) the DB row is marked
    ``cancelled`` immediately so it disappears from the admin list.
    """
    from datetime import UTC, datetime

    from app.services.lyrics_worker import (
        CANCEL_KEY_PREFIX,
        set_lyrics_progress,
    )

    row = (
        await session.execute(
            select(LyricsJob).where(LyricsJob.id == job_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404, detail="job not found"
        )

    if row.status in _TERMINAL_LYRICS_STATUSES:
        return {
            "status": "already_done",
            "job_status": row.status,
        }

    progress_id = row.progress_id

    # Set cancel flag for running worker (if any).
    redis = get_redis_client()
    if progress_id:
        try:
            await redis.set(
                f"{CANCEL_KEY_PREFIX}{progress_id}",
                "1",
                ex=600,
            )
            await set_lyrics_progress(
                progress_id,
                stage="cancelling",
                log_line=(
                    "cancellation requested by admin"
                ),
            )
        except Exception:
            logger.exception(
                "admin_lyrics_cancel_signal_failed",
                job_id=job_id,
                progress_id=progress_id,
            )

    # Immediately mark queued jobs as cancelled in DB so they
    # disappear from the admin list even if no worker is alive.
    if row.status == "queued":
        row.status = "cancelled"
        row.finished_at = datetime.now(UTC)
        row.error = "cancelled_by_admin"
        await session.commit()
        logger.info(
            "admin_lyrics_cancel_queued_direct",
            job_id=job_id,
            progress_id=progress_id,
        )
        return {"status": "cancelled", "job_status": "cancelled"}

    logger.info(
        "admin_lyrics_cancel_requested",
        job_id=job_id,
        progress_id=progress_id,
    )
    return {"status": "cancel_requested"}


@router.post("/lyrics-jobs/cancel-queued")
async def cancel_all_queued_lyrics_jobs(
    _admin: User = Depends(
        require_capability("tasks.manage")
    ),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Bulk-cancel every lyrics job currently in ``queued`` state.

    Also signals cancel on their progress channels so a worker that
    picks one up right after this call will exit immediately.
    """
    from datetime import UTC, datetime

    from app.services.lyrics_worker import CANCEL_KEY_PREFIX

    queued_rows = (
        await session.execute(
            select(LyricsJob).where(LyricsJob.status == "queued")
        )
    ).scalars().all()

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
    query = select(LyricsJob)
    count_query = select(func.count(LyricsJob.id))
    if status:
        query = query.where(LyricsJob.status == status)
        count_query = count_query.where(LyricsJob.status == status)
    if profile:
        query = query.where(LyricsJob.profile == profile)
        count_query = count_query.where(LyricsJob.profile == profile)
    query = (
        query.order_by(desc(LyricsJob.created_at))
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await session.execute(query)
    rows = list(result.scalars().all())
    total_result = await session.execute(count_query)
    total = int(total_result.scalar_one())
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
                "attempts": row.attempts,
                "error": row.error,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
                "duration_ms": row.duration_ms,
                "created_at": row.created_at,
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
    query = select(WorkerAuditLog)
    if worker_id:
        query = query.where(WorkerAuditLog.worker_id == worker_id)
    query = query.order_by(desc(WorkerAuditLog.created_at)).limit(limit)
    result = await session.execute(query)
    rows = list(result.scalars().all())
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
