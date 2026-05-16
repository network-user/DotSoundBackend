"""External playlist scan — runs in the API process as a background task.

The HTTP handler creates an ``ImportJob`` in ``scanning`` state, commits
it, then schedules :func:`run_external_playlist_scan` via
``asyncio.create_task``. The client polls ``GET /import/{job_id}/status``.

A thin Taskiq wrapper (:func:`scan_external_playlist_task`) remains for
manual/legacy queue use but is **not** used by :class:`ImportService`.
"""
import asyncio
import time
from datetime import datetime, timezone

import structlog

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.core.tkq import broker
from app.models.import_job import ImportJob
from app.services.external_providers import ProviderError, scan_playlist_url

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_SCAN_LOCK_PREFIX = "import:scan:lock"
_JOB_LOOKUP_RETRIES = 12
_JOB_LOOKUP_DELAY_S = 0.05


async def _try_acquire_scan_lock(job_id: int) -> bool:
    try:
        ttl = max(
            120,
            int(settings.import_external_scan_watchdog_seconds) + 30,
        )
        acquired = await get_redis_client().set(
            f"{_SCAN_LOCK_PREFIX}:{job_id}",
            "1",
            nx=True,
            ex=ttl,
        )
        return bool(acquired)
    except Exception:
        return True


async def _load_scanning_job(
    session,
    job_id: int,
) -> ImportJob | None:
    for _ in range(_JOB_LOOKUP_RETRIES):
        job = await session.get(ImportJob, job_id)
        if job is not None:
            return job
        await asyncio.sleep(_JOB_LOOKUP_DELAY_S)
    return None


async def run_external_playlist_scan(
    job_id: int,
    source: str,
    url: str,
) -> None:
    """Scan an external URL and persist the result on the ImportJob.

    Always executed inside the API worker process (background asyncio
    task), not via a separate Taskiq consumer.
    """
    t_start = time.monotonic()
    logger.info(
        "external_scan_task_start",
        job_id=job_id,
        source=source,
        url=url,
    )

    if not await _try_acquire_scan_lock(job_id):
        logger.info(
            "external_scan_task_duplicate_skip",
            job_id=job_id,
        )
        return

    async with AsyncSessionLocal() as session:
        job = await _load_scanning_job(session, job_id)
        if job is None:
            logger.error(
                "external_scan_task_job_missing", job_id=job_id
            )
            return

        if job.status != "scanning":
            logger.info(
                "external_scan_task_skipped_non_scanning",
                job_id=job_id,
                status=job.status,
            )
            return

        await session.refresh(job)
        if job.status != "scanning":
            logger.info(
                "external_scan_task_skipped_after_refresh",
                job_id=job_id,
                status=job.status,
            )
            return

        meta = dict(job.tracks_data or {})
        meta["scan_worker_started"] = datetime.now(
            timezone.utc
        ).isoformat()
        job.tracks_data = meta
        await session.commit()

        try:
            result = await scan_playlist_url(source, url)
        except ProviderError as exc:
            elapsed = round(time.monotonic() - t_start, 2)
            await session.refresh(job)
            if job.status != "scanning":
                logger.info(
                    "external_scan_task_abort_after_provider_error",
                    job_id=job_id,
                    status=job.status,
                )
                return
            job.status = "failed"
            job.tracks_data = {
                "error_code": exc.code,
                "error_message": exc.message,
                "source_url": url,
                "diagnostics": exc.diagnostics,
            }
            logger.info(
                "external_scan_task_provider_error",
                job_id=job_id,
                source=source,
                code=exc.code,
                message=exc.message,
                elapsed_s=elapsed,
                diag_requests=len(exc.diagnostics),
            )
            await session.commit()
            return
        except Exception as exc:
            elapsed = round(time.monotonic() - t_start, 2)
            await session.refresh(job)
            if job.status != "scanning":
                logger.info(
                    "external_scan_task_abort_after_exception",
                    job_id=job_id,
                    status=job.status,
                )
                return
            job.status = "failed"
            job.tracks_data = {
                "error_code": "provider_unavailable",
                "error_message": str(exc),
                "source_url": url,
            }
            logger.error(
                "external_scan_task_error",
                job_id=job_id,
                source=source,
                error=str(exc),
                elapsed_s=elapsed,
            )
            await session.commit()
            return

        elapsed = round(time.monotonic() - t_start, 2)
        await session.refresh(job)
        if job.status != "scanning":
            logger.info(
                "external_scan_task_abort_success_path",
                job_id=job_id,
                status=job.status,
            )
            return
        tracks = result.get("tracks", [])
        diagnostics = result.get("diagnostics", []) or []
        job.status = "ready"
        job.total_tracks = len(tracks)
        job.tracks_data = {
            "kind": result.get("kind"),
            "source_url": url,
            "tracks": tracks,
            "diagnostics": diagnostics,
        }
        await session.commit()

        logger.info(
            "external_scan_task_complete",
            job_id=job_id,
            source=source,
            total=len(tracks),
            elapsed_s=elapsed,
            diag_requests=len(diagnostics),
        )


@broker.task(task_name="external_scan_playlist")
async def scan_external_playlist_task(
    job_id: int,
    source: str,
    url: str,
) -> None:
    """Legacy Taskiq entrypoint — not used by ImportService."""
    await run_external_playlist_scan(job_id, source, url)
