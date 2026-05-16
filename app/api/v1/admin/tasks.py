"""Admin task-management endpoints (Taskiq + lyrics_jobs)."""

from __future__ import annotations

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
                "too many job ids; "
                f"max {_PLAYBACK_REPAIR_SUMMARY_LIMIT}"
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
            int(track_id): sc_url
            for track_id, sc_url in track_rows.all()
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
            if (
                current is None
                or (
                    row.status == "running"
                    and current.get("status") != "running"
                )
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
                "too many job ids; "
                f"max {_PLAYBACK_REPAIR_SUMMARY_LIMIT}"
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
