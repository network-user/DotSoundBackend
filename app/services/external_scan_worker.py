"""Background taskiq task for external playlist scanning.

Separates the slow network I/O of scanning from the HTTP request
so the endpoint returns immediately with a ``scanning`` job, and
the frontend polls ``GET /import/{job_id}/status`` for completion.
"""
import time

import structlog

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.import_job import ImportJob
from app.services.external_providers import ProviderError, scan_playlist_url

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@broker.task(task_name="external_scan_playlist")
async def scan_external_playlist_task(
    job_id: int,
    source: str,
    url: str,
) -> None:
    """Scan an external playlist/album URL and update the ImportJob.

    Runs in a Taskiq worker (or as an asyncio fallback when the broker
    is unavailable). On completion sets job.status to
    ``"ready"`` or ``"failed"``.
    """
    t_start = time.monotonic()
    logger.info(
        "external_scan_task_start",
        job_id=job_id,
        source=source,
        url=url,
    )

    async with AsyncSessionLocal() as session:
        job = await session.get(ImportJob, job_id)
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

        try:
            result = await scan_playlist_url(source, url)
        except ProviderError as exc:
            elapsed = round(time.monotonic() - t_start, 2)
            job.status = "failed"
            job.tracks_data = {
                "error_code": exc.code,
                "error_message": exc.message,
                "source_url": url,
            }
            logger.info(
                "external_scan_task_provider_error",
                job_id=job_id,
                source=source,
                code=exc.code,
                message=exc.message,
                elapsed_s=elapsed,
            )
            await session.commit()
            return
        except Exception as exc:
            elapsed = round(time.monotonic() - t_start, 2)
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
        tracks = result.get("tracks", [])
        job.status = "ready"
        job.total_tracks = len(tracks)
        job.tracks_data = {
            "kind": result.get("kind"),
            "source_url": url,
            "tracks": tracks,
        }
        await session.commit()

        logger.info(
            "external_scan_task_complete",
            job_id=job_id,
            source=source,
            total=len(tracks),
            elapsed_s=elapsed,
        )
