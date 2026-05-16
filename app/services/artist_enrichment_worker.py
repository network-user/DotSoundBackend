"""Taskiq worker for artist enrichment.

Matches the lyrics-worker pattern: one background task, optional
warmup at worker startup. PrivateCore is an opaque dependency — this
module must not name specific external providers.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import or_, select
from taskiq import TaskiqEvents, TaskiqState

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.artist import Artist
from app.services.artist_enrichment_service import (
    ArtistEnrichmentService,
    ArtistNotFound,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_STUCK_THRESHOLD_HOURS = 2
_REENRICH_BATCH_LIMIT = 200


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _preload_artist_info_provider(
    _state: TaskiqState,
) -> None:
    """Preload heavy assets for the artist info provider once per worker."""
    try:
        from dotsound_private_core.services.artist_info_provider import (  # noqa: E501
            warmup_artist_info_provider,
        )
    except Exception:
        logger.info("artist_info_provider_warmup_unavailable")
        return

    try:
        await asyncio.to_thread(warmup_artist_info_provider)
        logger.info("artist_info_provider_warmup_done")
    except Exception:
        logger.exception("artist_info_provider_warmup_failed")


@broker.task
async def enrich_artist_task(
    artist_id: int,
    progress_id: str = "",
    bypass_cache: bool = False,
    skip_catalog_sync: bool = False,
) -> dict:
    import time

    structlog.contextvars.bind_contextvars(
        artist_id=artist_id, progress_id=progress_id
    )
    logger.info(
        "enrich_artist_task_picked_up",
        artist_id=artist_id,
        progress_id=progress_id,
        bypass_cache=bypass_cache,
        skip_catalog_sync=skip_catalog_sync,
    )
    t_start = time.monotonic()
    async with AsyncSessionLocal() as session:
        svc = ArtistEnrichmentService(session)
        try:
            await svc.enrich(
                artist_id,
                bypass_cache=bypass_cache,
                progress_id=progress_id or None,
                skip_catalog_sync=skip_catalog_sync,
            )
            from app.services.search_index_notify import (
                schedule_reindex_artist,
            )

            await schedule_reindex_artist(artist_id)
            logger.info(
                "enrich_artist_task_done",
                artist_id=artist_id,
                elapsed_s=round(time.monotonic() - t_start, 2),
            )
            return {"status": "ok"}
        except ArtistNotFound:
            logger.info("artist_enrichment_missing_artist")
            return {"status": "not_found"}
        except Exception:
            logger.exception(
                "artist_enrichment_task_error",
                elapsed_s=round(time.monotonic() - t_start, 2),
            )
            return {"status": "error"}


@broker.task
async def re_enrich_pending_artists_task() -> dict:
    """Re-enqueue enrichment for artists stuck in pending/in_progress.

    Runs on a daily cron schedule. Catches artists whose
    ``enrich_artist_task`` was lost (Redis temporarily unavailable at
    creation time) or whose worker process died mid-enrichment.
    """
    from app.services.background_jobs import IdempotencySkipped, enqueue

    cutoff = datetime.now(UTC) - timedelta(hours=_STUCK_THRESHOLD_HOURS)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Artist.id)
            .where(
                or_(
                    Artist.enrichment_status == "pending",
                    Artist.enrichment_status == "in_progress",
                ),
                Artist.updated_at < cutoff,
            )
            .limit(_REENRICH_BATCH_LIMIT)
        )
        artist_ids = list(result.scalars().all())

    enqueued = 0
    skipped = 0
    for artist_id in artist_ids:
        try:
            await enqueue(
                enrich_artist_task,
                payload={"artist_id": artist_id},
                idempotency_key=f"artist-enrich:{artist_id}",
            )
            enqueued += 1
        except IdempotencySkipped:
            skipped += 1
        except Exception:
            logger.exception(
                "pending_artist_reenrich_enqueue_failed",
                artist_id=artist_id,
            )

    logger.info(
        "re_enrich_pending_artists_done",
        enqueued=enqueued,
        skipped=skipped,
        total_found=len(artist_ids),
    )
    return {
        "enqueued": enqueued,
        "skipped": skipped,
        "total_found": len(artist_ids),
    }
