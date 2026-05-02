from __future__ import annotations

import structlog
from typing import Any

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.repositories.artist_catalog import ArtistCatalogRepository
from app.services import artist_catalog_sync_progress as acsp
from app.services.artist_catalog_sync_service import ArtistCatalogSyncService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_STATION_BATCH_SIZE = 20


@broker.task
async def sync_artist_catalog_task(artist_id: int) -> dict[str, Any]:
    try:
        async with AsyncSessionLocal() as session:
            svc = ArtistCatalogSyncService(session)
            result = await svc.sync_full_artist(artist_id)
        await acsp.set_success(
            artist_id,
            mode="full",
            soundcloud_album_id=None,
            detail=result,
        )
        return result
    except Exception as exc:
        await acsp.set_error(
            artist_id,
            mode="full",
            soundcloud_album_id=None,
            message=repr(exc),
        )
        raise


@broker.task
async def sync_artist_similar_station_task(
    artist_id: int,
) -> dict[str, Any]:
    try:
        async with AsyncSessionLocal() as session:
            svc = ArtistCatalogSyncService(session)
            result = await svc.sync_artist_similar_station(
                artist_id
            )
        await acsp.set_success(
            artist_id,
            mode="station",
            soundcloud_album_id=None,
            detail=result,
        )
        return result
    except Exception as exc:
        await acsp.set_error(
            artist_id,
            mode="station",
            soundcloud_album_id=None,
            message=repr(exc),
        )
        raise


@broker.task
async def sync_stale_stations_batch_task() -> dict[str, Any]:
    """Weekly sweep: enqueue station sync for all stale artist stations."""
    from app.config import settings

    async with AsyncSessionLocal() as session:
        repo = ArtistCatalogRepository(session)
        artist_ids = await repo.find_stale_station_artist_ids(
            settings.artist_station_stale_threshold_days
        )

    enqueued = 0
    for i in range(0, len(artist_ids), _STATION_BATCH_SIZE):
        batch = artist_ids[i : i + _STATION_BATCH_SIZE]
        for artist_id in batch:
            await sync_artist_similar_station_task.kiq(artist_id)
            enqueued += 1

    logger.info(
        "station_stale_sweep_complete",
        enqueued=enqueued,
        total_stale=len(artist_ids),
    )
    return {"enqueued": enqueued}


@broker.task
async def sync_artist_catalog_release_task(
    artist_id: int,
    soundcloud_album_id: int,
) -> dict[str, Any]:
    try:
        async with AsyncSessionLocal() as session:
            svc = ArtistCatalogSyncService(session)
            result = await svc.sync_single_release(
                artist_id,
                soundcloud_album_id,
            )
        await acsp.set_success(
            artist_id,
            mode="release",
            soundcloud_album_id=soundcloud_album_id,
            detail=result,
        )
        return result
    except Exception as exc:
        await acsp.set_error(
            artist_id,
            mode="release",
            soundcloud_album_id=soundcloud_album_id,
            message=repr(exc),
        )
        raise
