"""Cron-driven scheduler for background jobs.

A single asyncio loop (held by one worker process via a Redis lock)
polls ``ScheduledJob`` rows every ``POLL_INTERVAL_SECONDS`` seconds,
evaluates their cron expression and kicks the underlying Taskiq
task through ``enqueue()`` when due.

Continuous orchestrator loops in ``import_queue_dispatcher`` and
``lyrics_global_orchestrator`` are intentionally **not** managed
here — they have specialised pacing/fan-out semantics. Cron-style
periodic work goes through this scheduler; long-lived orchestrators
stay where they are.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from croniter import croniter
from sqlalchemy import select
from taskiq import TaskiqEvents, TaskiqState

from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.core.tkq import broker
from app.models.scheduled_job import ScheduledJob
from app.services.background_jobs import (
    IdempotencySkipped,
    enqueue,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

POLL_INTERVAL_SECONDS = 30
LEADER_LOCK_KEY = "bgjob:scheduler:leader"
LEADER_LOCK_TTL = 60

_scheduler_task: asyncio.Task | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _compute_next_run(cron_expr: str, base: datetime) -> datetime:
    itr = croniter(cron_expr, base)
    return itr.get_next(datetime)


async def _try_acquire_leader(worker_id: str) -> bool:
    redis = get_redis_client()
    try:
        ok = await redis.set(
            LEADER_LOCK_KEY,
            worker_id,
            ex=LEADER_LOCK_TTL,
            nx=True,
        )
        if ok:
            return True
        # Refresh if we already hold it
        current = await redis.get(LEADER_LOCK_KEY)
        if current == worker_id:
            await redis.expire(LEADER_LOCK_KEY, LEADER_LOCK_TTL)
            return True
        return False
    except Exception:
        logger.exception("scheduler_leader_lock_failed")
        return False


async def _release_leader(worker_id: str) -> None:
    redis = get_redis_client()
    try:
        current = await redis.get(LEADER_LOCK_KEY)
        if current == worker_id:
            await redis.delete(LEADER_LOCK_KEY)
    except Exception:
        pass


async def _process_due_schedules() -> None:
    now = _now()
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.enabled.is_(True)
                )
            )
        ).scalars().all()

        for row in rows:
            try:
                if not croniter.is_valid(row.cron):
                    row.last_status = "invalid_cron"
                    row.last_error = (
                        f"invalid cron expression: {row.cron}"
                    )
                    continue

                # Bootstrap next_run_at on first observation.
                if row.next_run_at is None:
                    row.next_run_at = _compute_next_run(
                        row.cron, now
                    )
                    continue

                if row.next_run_at > now:
                    continue

                task = broker.find_task(row.task_name)
                if task is None:
                    row.last_status = "task_missing"
                    row.last_error = (
                        f"task not registered: {row.task_name}"
                    )
                    row.next_run_at = _compute_next_run(
                        row.cron, now
                    )
                    continue

                try:
                    job_id = await enqueue(
                        task,
                        payload=row.payload or {},
                        queue=row.queue or "default",
                        scheduled_job_id=row.id,
                        idempotency_key=(
                            f"sched:{row.id}:"
                            f"{int(row.next_run_at.timestamp())}"
                        ),
                        idempotency_ttl_seconds=300,
                    )
                    row.last_status = "queued"
                    row.last_error = None
                    row.last_job_id = job_id
                except IdempotencySkipped:
                    row.last_status = "skipped_duplicate"
                except Exception as exc:  # noqa: BLE001
                    row.last_status = "kick_failed"
                    row.last_error = (
                        f"{type(exc).__name__}: {exc}"
                    )[:4000]
                    logger.exception(
                        "scheduler_kick_failed",
                        scheduled_job=row.name,
                    )

                row.last_run_at = now
                row.next_run_at = _compute_next_run(row.cron, now)
            except Exception:
                logger.exception(
                    "scheduler_row_failed",
                    scheduled_job=getattr(row, "name", None),
                )

        await session.commit()


async def _scheduler_loop(worker_id: str) -> None:
    logger.info("scheduler_started", worker_id=worker_id)
    try:
        while True:
            try:
                is_leader = await _try_acquire_leader(worker_id)
                if is_leader:
                    await _process_due_schedules()
            except Exception:
                logger.exception("scheduler_iteration_failed")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        await _release_leader(worker_id)
        raise


async def run_now(scheduled_job_id: str) -> str | None:
    """Kick a scheduled job immediately, ignoring the cron clock.

    Returns the resulting BackgroundJob id, or ``None`` if the
    scheduled job or its task could not be found.
    """
    async with AsyncSessionLocal() as session:
        row = await session.get(ScheduledJob, scheduled_job_id)
        if row is None:
            return None
        task = broker.find_task(row.task_name)
        if task is None:
            return None
        try:
            job_id = await enqueue(
                task,
                payload=row.payload or {},
                queue=row.queue or "default",
                scheduled_job_id=row.id,
            )
        except IdempotencySkipped:
            return None
        row.last_run_at = _now()
        row.last_status = "queued"
        row.last_error = None
        row.last_job_id = job_id
        await session.commit()
        return job_id


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start_scheduler(_st: TaskiqState) -> None:
    global _scheduler_task
    if _scheduler_task is not None:
        return
    import os

    worker_id = f"sched-{os.getpid()}"
    _scheduler_task = asyncio.create_task(
        _scheduler_loop(worker_id)
    )


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop_scheduler(_st: TaskiqState) -> None:
    global _scheduler_task
    task = _scheduler_task
    _scheduler_task = None
    if task is None:
        return
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):  # noqa: BLE001
        pass


# Marker so the module is non-empty even when imported only for
# its broker hooks.
__all__: list[Any] = ["run_now"]
