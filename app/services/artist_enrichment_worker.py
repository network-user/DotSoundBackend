"""Taskiq worker for artist enrichment.

Matches the lyrics-worker pattern: one background task, optional
warmup at worker startup. PrivateCore is an opaque dependency — this
module must not name specific external providers.
"""

from __future__ import annotations

import asyncio

import structlog
from taskiq import TaskiqEvents, TaskiqState

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.services.artist_enrichment_service import (
    ArtistEnrichmentService,
    ArtistNotFound,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


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
    )
    t_start = time.monotonic()
    async with AsyncSessionLocal() as session:
        svc = ArtistEnrichmentService(session)
        try:
            await svc.enrich(
                artist_id,
                bypass_cache=bypass_cache,
                progress_id=progress_id or None,
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
