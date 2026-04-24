from __future__ import annotations

import asyncio

import structlog
from taskiq import TaskiqEvents, TaskiqState

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.artist import Artist
from app.models.track import Track
from app.search.es_client import es_available, get_es
from app.search.indices import ensure_tracks_artist_indices, wait_for_cluster
from app.services.search_index_service import (
    delete_artist_document,
    delete_track_document,
    index_artist_document,
    index_track_document,
    reindex_all_tracks_artist_backfill,
    reindex_artist_affected_tracks,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _es_worker_warmup(_state: TaskiqState) -> None:
    if not es_available():
        return
    try:
        es = get_es()
        await wait_for_cluster(es, timeout=20.0)
        await ensure_tracks_artist_indices(es)
    except Exception as exc:  # noqa: BLE001
        logger.warning("es_worker_warmup_failed", error=str(exc))


@broker.task
async def reindex_track_task(track_id: int) -> None:
    if not es_available():
        return
    t: Track | None = None
    for attempt in range(3):
        async with AsyncSessionLocal() as session:
            t = await session.get(Track, track_id)
        if t is not None:
            break
        await asyncio.sleep(0.12 * (attempt + 1))
    if t is None:
        await delete_track_document(track_id)
        return
    async with AsyncSessionLocal() as session:
        t2 = await session.get(Track, track_id)
        if t2 is None:
            await delete_track_document(track_id)
            return
        await index_track_document(session, t2)
        await session.commit()


@broker.task
async def reindex_artist_task(artist_id: int) -> None:
    if not es_available():
        return
    a: Artist | None = None
    for attempt in range(3):
        async with AsyncSessionLocal() as session:
            a = await session.get(Artist, artist_id)
        if a is not None:
            break
        await asyncio.sleep(0.12 * (attempt + 1))
    if a is None:
        await delete_artist_document(artist_id)
        return
    async with AsyncSessionLocal() as session:
        await index_artist_document(session, artist_id)
        await session.commit()
        await reindex_artist_affected_tracks(artist_id)


@broker.task
async def delete_track_es_task(track_id: int) -> None:
    if not es_available():
        return
    await delete_track_document(track_id)


@broker.task
async def reindex_backfill_all_task() -> int:
    if not es_available():
        return 0
    return await reindex_all_tracks_artist_backfill()
