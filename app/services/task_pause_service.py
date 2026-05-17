"""Pause/resume background task types at admin's request.

Stores a Redis hash ``bgjob:paused_tasks`` where each field is a task
name (``app.services.foo:bar_task`` or the public Taskiq label) and
each value is a JSON blob with ``paused_at`` / ``by_admin_id``.

Integration points:

* :func:`app.services.background_jobs.enqueue` consults
  :func:`is_task_paused` before kicking the underlying Taskiq task and
  raises :class:`TaskPaused` if the type is currently blocked.
* :func:`app.services.compute_queue_service.claim_next` excludes paused
  ``job_type`` values from the SELECT.
* :func:`app.services.compute_job_dispatcher.dispatch_compute_job`
  short-circuits with status ``paused`` when the job's type is paused.

All operations fail open: if Redis is unreachable the pause set is
treated as empty so we never wedge production behind a stale Redis.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.redis import get_redis_client

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

PAUSE_HASH_KEY = "bgjob:paused_tasks"


class TaskPaused(Exception):
    """Raised by ``enqueue()`` when the task type is paused."""

    def __init__(self, task_name: str) -> None:
        super().__init__(f"task paused: {task_name}")
        self.task_name = task_name


async def is_task_paused(task_name: str) -> bool:
    if not task_name:
        return False
    try:
        redis = get_redis_client()
        raw = await redis.hget(PAUSE_HASH_KEY, task_name)
        return raw is not None
    except Exception:
        logger.warning("task_pause_lookup_failed", task_name=task_name)
        return False


async def paused_task_set() -> set[str]:
    """Return the full set of currently paused task names."""
    try:
        redis = get_redis_client()
        raw = await redis.hkeys(PAUSE_HASH_KEY)
    except Exception:
        logger.warning("task_pause_set_failed")
        return set()
    out: set[str] = set()
    for entry in raw or []:
        name = entry.decode() if isinstance(entry, bytes) else str(entry)
        out.add(name)
    return out


async def list_paused_tasks() -> dict[str, dict[str, Any]]:
    """Return ``{task_name: meta}`` for every paused task."""
    try:
        redis = get_redis_client()
        raw = await redis.hgetall(PAUSE_HASH_KEY)
    except Exception:
        logger.warning("task_pause_list_failed")
        return {}
    out: dict[str, dict[str, Any]] = {}
    for k, v in (raw or {}).items():
        name = k.decode() if isinstance(k, bytes) else str(k)
        raw_value = v.decode() if isinstance(v, bytes) else str(v)
        try:
            out[name] = json.loads(raw_value)
        except Exception:
            out[name] = {"paused_at": None, "by_admin_id": None}
    return out


async def pause_task(
    task_name: str,
    *,
    by_admin_id: int | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    if not task_name:
        raise ValueError("task_name is required")
    meta = {
        "paused_at": datetime.now(UTC).isoformat(),
        "by_admin_id": by_admin_id,
        "reason": (reason or "")[:200] or None,
    }
    try:
        redis = get_redis_client()
        await redis.hset(PAUSE_HASH_KEY, task_name, json.dumps(meta))
    except Exception:
        logger.exception("task_pause_write_failed", task_name=task_name)
        raise
    logger.warning(
        "task_paused",
        task_name=task_name,
        by_admin_id=by_admin_id,
    )
    return meta


async def resume_task(task_name: str) -> bool:
    if not task_name:
        return False
    try:
        redis = get_redis_client()
        removed = await redis.hdel(PAUSE_HASH_KEY, task_name)
    except Exception:
        logger.exception("task_resume_write_failed", task_name=task_name)
        return False
    if removed:
        logger.warning("task_resumed", task_name=task_name)
    return bool(removed)


async def drain_task(task_name: str) -> dict[str, int]:
    """Cancel queued + in-flight jobs of the given type.

    Returns ``{"background_jobs": N, "compute_jobs": M}``. Caller is
    expected to call :func:`pause_task` separately (drain is the
    "hard" half of a hard-pause: pause first to stop the inflow, then
    drain what is already in flight).

    * ``background_jobs`` matching ``name == task_name`` AND status in
      (``queued``, ``running``, ``cancelling``) are flagged via
      :func:`app.services.cancellation.signal_cancel`. Taskiq
      middleware will mark them ``cancelled`` once the worker checks
      in (queued jobs flip immediately on next start).
    * ``compute_jobs`` matching ``job_type == task_name`` (including
      legacy aliases) AND status in (``pending``, ``claimed``) are set
      directly to ``cancelled`` with ``next_attempt_at`` cleared so
      they will not be re-claimed by ``claim_next``.
    """
    import contextlib

    from sqlalchemy import update

    from app.core.db import AsyncSessionLocal
    from app.models.background_job import BackgroundJob
    from app.models.compute_job import ComputeJob
    from app.services import compute_queue_service as cq
    from app.services.cancellation import signal_cancel

    bg_drained = 0
    compute_drained = 0
    async with AsyncSessionLocal() as session:
        bg_rows = (
            await session.execute(
                BackgroundJob.__table__.select().where(
                    BackgroundJob.name == task_name,
                    BackgroundJob.status.in_(
                        ("queued", "running", "cancelling")
                    ),
                )
            )
        ).fetchall()
        for row in bg_rows:
            with contextlib.suppress(Exception):
                await signal_cancel(row.id)
                bg_drained += 1

        canonical = cq.canonical_job_type(task_name)
        candidates = {canonical, task_name}
        for alias, canon in cq.LEGACY_JOB_TYPE_ALIASES.items():
            if canon == canonical:
                candidates.add(alias)
        upd = (
            update(ComputeJob)
            .where(
                ComputeJob.job_type.in_(sorted(candidates)),
                ComputeJob.status.in_((cq.STATUS_PENDING, cq.STATUS_CLAIMED)),
            )
            .values(
                status="cancelled",
                next_attempt_at=None,
                claim_deadline_at=None,
            )
            .execution_options(synchronize_session=False)
        )
        result = await session.execute(upd)
        compute_drained = int(result.rowcount or 0)
        await session.commit()

    logger.warning(
        "task_drained",
        task_name=task_name,
        background_jobs=bg_drained,
        compute_jobs=compute_drained,
    )
    return {
        "background_jobs": bg_drained,
        "compute_jobs": compute_drained,
    }


async def affected_jobs_preview(task_name: str) -> dict[str, int]:
    """Lightweight preview: how many jobs a drain would touch right now."""
    from sqlalchemy import func, select

    from app.core.db import AsyncSessionLocal
    from app.models.background_job import BackgroundJob
    from app.models.compute_job import ComputeJob
    from app.services import compute_queue_service as cq

    async with AsyncSessionLocal() as session:
        bg = await session.execute(
            select(func.count(BackgroundJob.id)).where(
                BackgroundJob.name == task_name,
                BackgroundJob.status.in_(("queued", "running", "cancelling")),
            )
        )
        bg_count = int(bg.scalar_one() or 0)
        canonical = cq.canonical_job_type(task_name)
        candidates = {canonical, task_name}
        for alias, canon in cq.LEGACY_JOB_TYPE_ALIASES.items():
            if canon == canonical:
                candidates.add(alias)
        cj = await session.execute(
            select(func.count(ComputeJob.id)).where(
                ComputeJob.job_type.in_(sorted(candidates)),
                ComputeJob.status.in_((cq.STATUS_PENDING, cq.STATUS_CLAIMED)),
            )
        )
        cj_count = int(cj.scalar_one() or 0)
    return {
        "background_jobs": bg_count,
        "compute_jobs": cj_count,
    }


__all__ = [
    "PAUSE_HASH_KEY",
    "TaskPaused",
    "is_task_paused",
    "paused_task_set",
    "list_paused_tasks",
    "pause_task",
    "resume_task",
    "drain_task",
    "affected_jobs_preview",
]
