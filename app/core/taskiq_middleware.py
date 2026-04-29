"""Taskiq middleware that ties task execution to BackgroundJob rows.

Reads ``bgjob_id`` from the incoming message labels (set by
``app.services.background_jobs.enqueue``) and updates the row at
each lifecycle stage:

- ``pre_execute``  -> status=running, started_at, attempts++
- ``post_execute`` (success) -> status=done, finished_at, duration
- ``on_error`` -> if attempts < max_attempts: re-kick same task
                  with same labels; otherwise status=failed_terminal
                  and an admin alert is fired.

Tasks that are kicked the legacy way (``task.kiq(...)`` without the
``enqueue()`` wrapper) carry no ``bgjob_id`` label and are passed
through untouched — preserves backwards-compatibility while the 16
existing workers migrate incrementally.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from taskiq import TaskiqMessage, TaskiqMiddleware, TaskiqResult

from app.core.db import AsyncSessionLocal
from app.models.background_job import BackgroundJob

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _label(message: TaskiqMessage, key: str) -> str | None:
    val = message.labels.get(key) if message.labels else None
    return str(val) if val is not None else None


def _int_label(message: TaskiqMessage, key: str, default: int) -> int:
    raw = _label(message, key)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


class BackgroundJobLifecycleMiddleware(TaskiqMiddleware):
    """Updates BackgroundJob row on every task lifecycle event."""

    async def pre_execute(
        self, message: TaskiqMessage
    ) -> TaskiqMessage:
        job_id = _label(message, "bgjob_id")
        if not job_id:
            return message
        try:
            async with AsyncSessionLocal() as session:
                row = await session.get(BackgroundJob, job_id)
                if row is None:
                    return message
                row.status = "running"
                row.started_at = datetime.now(UTC)
                row.attempts = (row.attempts or 0) + 1
                await session.commit()
        except Exception:
            logger.exception(
                "bgjob_pre_execute_update_failed",
                job_id=job_id,
            )
        return message

    async def post_execute(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
    ) -> None:
        job_id = _label(message, "bgjob_id")
        if not job_id:
            return
        if result.is_err:
            return  # handled by on_error
        try:
            async with AsyncSessionLocal() as session:
                row = await session.get(BackgroundJob, job_id)
                if row is None:
                    return
                now = datetime.now(UTC)
                row.status = "done"
                row.finished_at = now
                if row.started_at is not None:
                    row.duration_ms = int(
                        (now - row.started_at).total_seconds()
                        * 1000
                    )
                row.error = None
                await session.commit()
        except Exception:
            logger.exception(
                "bgjob_post_execute_update_failed",
                job_id=job_id,
            )

    async def on_error(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
        exception: BaseException,
    ) -> None:
        job_id = _label(message, "bgjob_id")
        if not job_id:
            return
        max_attempts = _int_label(
            message, "bgjob_max_attempts", default=3
        )
        err_str = f"{type(exception).__name__}: {exception}"[:4000]
        retried = False

        try:
            async with AsyncSessionLocal() as session:
                row = await session.get(BackgroundJob, job_id)
                if row is None:
                    return
                attempts = row.attempts or 0
                effective_max = row.max_attempts or max_attempts
                now = datetime.now(UTC)

                if attempts < effective_max:
                    row.status = "queued"
                    row.error = err_str
                    await session.commit()
                    # schedule retry with backoff
                    backoff = min(
                        60, 2 ** max(0, attempts - 1)
                    )
                    asyncio.create_task(
                        _delayed_rekick(
                            self.broker,
                            message,
                            delay_seconds=backoff,
                        )
                    )
                    retried = True
                else:
                    row.status = "failed_terminal"
                    row.finished_at = now
                    if row.started_at is not None:
                        row.duration_ms = int(
                            (now - row.started_at).total_seconds()
                            * 1000
                        )
                    row.error = err_str
                    await session.commit()
        except Exception:
            logger.exception(
                "bgjob_on_error_update_failed",
                job_id=job_id,
            )
            return

        if not retried:
            await _fire_terminal_alert(
                job_id=job_id,
                task_name=message.task_name,
                error=err_str,
            )


async def _delayed_rekick(
    broker: Any,
    message: TaskiqMessage,
    *,
    delay_seconds: float,
) -> None:
    """Re-enqueue the same message after a backoff."""
    try:
        await asyncio.sleep(delay_seconds)
        task = broker.find_task(message.task_name)
        if task is None:
            logger.warning(
                "bgjob_retry_task_missing",
                task=message.task_name,
            )
            return
        kicker = task.kicker()
        if message.labels:
            kicker = kicker.with_labels(**message.labels)
        await kicker.kiq(*message.args, **(message.kwargs or {}))
    except Exception:
        logger.exception(
            "bgjob_retry_kick_failed",
            task=message.task_name,
        )


async def _fire_terminal_alert(
    *, job_id: str, task_name: str, error: str
) -> None:
    """Notify admins about a job that exhausted its retry budget."""
    try:
        from app.services.admin_alert_service import (
            send_admin_alert_task,
        )

        await send_admin_alert_task.kiq(
            event_type="background_job.failed_terminal",
            severity="warning",
            title=f"Background job failed: {task_name}",
            details=(
                f"job_id={job_id}\ntask={task_name}\nerror={error}"
            ),
            user_id=None,
            ip=None,
            ua=None,
        )
    except Exception:
        logger.exception(
            "bgjob_terminal_alert_failed",
            job_id=job_id,
        )
