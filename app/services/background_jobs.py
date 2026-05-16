"""Unified enqueue wrapper for Taskiq-driven background jobs.

Inserts a ``BackgroundJob`` row, then kicks the underlying Taskiq
task with the row id smuggled in labels so that lifecycle middleware
(``app.core.taskiq_middleware``) can update the row on
start/success/failure.

Usage::

    from app.services.background_jobs import enqueue
    from app.services.search_index_worker import reindex_track

    job_id = await enqueue(
        reindex_track,
        payload={"track_id": 42},
        idempotency_key=f"reindex:track:42",
        max_attempts=3,
    )

Existing 16 worker modules continue to call ``task.kiq(...)``
directly — they will be migrated to ``enqueue()`` incrementally.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models.background_job import BackgroundJob
from app.services.idempotency import acquire_idempotency_slot

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class IdempotencySkipped(Exception):
    """Raised when an idempotency slot was already taken."""

    def __init__(self, key: str) -> None:
        super().__init__(f"idempotency slot taken: {key}")
        self.key = key


class TaskKicker(Protocol):
    def with_labels(self, **labels: str) -> TaskKicker: ...

    async def kiq(self, **payload: object) -> object: ...


class EnqueueTask(Protocol):
    task_name: str

    def kicker(self) -> TaskKicker: ...


def _new_job_id() -> str:
    return uuid.uuid4().hex


async def enqueue(
    task: EnqueueTask,
    *,
    payload: dict[str, Any] | None = None,
    queue: str = "default",
    max_attempts: int = 3,
    idempotency_key: str | None = None,
    idempotency_ttl_seconds: int = 600,
    parent_job_id: str | None = None,
    scheduled_job_id: str | None = None,
    created_by_user_id: int | None = None,
    job_id_payload_key: str | None = None,
    session: AsyncSession | None = None,
) -> str:
    """Insert a BackgroundJob row and kick ``task`` via Taskiq.

    ``payload`` is forwarded to the task as ``**kwargs`` and also
    stored on the row for replay/debugging.

    Raises ``IdempotencySkipped`` if ``idempotency_key`` is already
    in flight (caller decides whether to swallow or propagate).
    """
    payload = dict(payload or {})

    if idempotency_key is not None:
        ok = await acquire_idempotency_slot(
            idempotency_key, ttl_seconds=idempotency_ttl_seconds
        )
        if not ok:
            logger.info(
                "background_job_idempotent_skip",
                key=idempotency_key,
                task=task.task_name,
            )
            raise IdempotencySkipped(idempotency_key)

    job_id = _new_job_id()
    task_payload = dict(payload)
    if job_id_payload_key is not None:
        payload.pop(job_id_payload_key, None)
        task_payload[job_id_payload_key] = job_id
    row = BackgroundJob(
        id=job_id,
        name=task.task_name,
        queue=queue,
        status="queued",
        payload=payload,
        max_attempts=max_attempts,
        scheduled_at=datetime.now(UTC),
        parent_job_id=parent_job_id,
        scheduled_job_id=scheduled_job_id,
        created_by_user_id=created_by_user_id,
        idempotency_key=idempotency_key,
    )

    own_session = session is None
    sess = session or AsyncSessionLocal()
    try:
        sess.add(row)
        if own_session:
            await sess.commit()
        else:
            await sess.flush()
    finally:
        if own_session:
            await sess.close()

    kicker = task.kicker().with_labels(
        bgjob_id=job_id,
        bgjob_max_attempts=str(max_attempts),
        bgjob_queue=queue,
    )
    try:
        result = await kicker.kiq(**task_payload)
    except Exception:
        logger.exception(
            "background_job_kick_failed",
            job_id=job_id,
            task=task.task_name,
        )
        # The row stays as 'queued' so admin can retry / inspect.
        raise

    taskiq_task_id = getattr(result, "task_id", None) or getattr(
        result, "id", None
    )
    if taskiq_task_id:
        async with AsyncSessionLocal() as s2:
            db_row = await s2.get(BackgroundJob, job_id)
            if db_row is not None:
                db_row.taskiq_task_id = str(taskiq_task_id)
                await s2.commit()

    return job_id
