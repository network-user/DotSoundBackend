"""Admin cancellation for ``lyrics_jobs`` (Taskiq and remote ASR)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.lyrics_job import LyricsJob
from app.services.lyrics_worker import (
    CANCEL_KEY_PREFIX,
    set_lyrics_progress,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

_TERMINAL: frozenset[str] = frozenset(
    {"done", "error", "cancelled", "not_found"}
)


async def cancel_lyrics_job_for_admin(
    session: AsyncSession,
    job_id: str,
) -> dict[str, Any] | None:
    """Cancel a lyrics / compute job by id.

    - ``queued``: row becomes ``cancelled`` immediately.
    - ``running`` (e.g. remote_whisper on a worker): row becomes
      ``cancelled`` and progress is finalised so the job leaves the
      in-flight list; the remote process may still finish locally but
      ``/result`` will reject with 409.
    - Other in-flight: sets Redis cancel + ``cancelling`` progress.

    Returns ``None`` if the job does not exist.
    """
    row = (
        await session.execute(
            select(LyricsJob).where(LyricsJob.id == job_id)
        )
    ).scalar_one_or_none()
    if row is None:
        return None

    if row.status in _TERMINAL:
        return {
            "status": "already_done",
            "job_status": row.status,
        }

    progress_id = row.progress_id

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

    if row.status == "running":
        now = datetime.now(UTC)
        row.status = "cancelled"
        row.finished_at = now
        row.error = "cancelled_by_admin"
        if progress_id:
            try:
                await set_lyrics_progress(
                    progress_id,
                    stage="error",
                    terminal_state="cancelled",
                    log_line=(
                        "cancelled by admin (lease released; "
                        "late worker result will be ignored)"
                    ),
                )
            except Exception:
                logger.exception(
                    "admin_lyrics_cancel_progress_failed",
                    job_id=job_id,
                )
        await session.commit()
        logger.info(
            "admin_lyrics_cancel_running",
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
