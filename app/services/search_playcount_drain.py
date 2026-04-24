from __future__ import annotations

import asyncio
import contextlib

import structlog

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.models.track import Track
from app.search.es_client import es_available
from app.services.search_index_service import index_track_document

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)
_DIRTY_KEY = "es:playcount_dirty"


async def mark_playcount_dirty_async(track_id: int) -> None:
    if not es_available():
        return
    try:
        r = get_redis_client()
        await r.sadd(_DIRTY_KEY, str(track_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "es_playcount_mark_dirty_failed",
            track_id=track_id,
            error=str(exc),
        )


async def _drain_batch() -> int:
    if not es_available():
        return 0
    r = get_redis_client()
    raw = await r.srandmember(_DIRTY_KEY, 200)  # type: ignore[call-arg]
    if not raw:
        return 0
    if isinstance(raw, str | bytes):
        ids_str = [raw] if raw else []
    else:
        ids_str = [str(x) for x in raw if x is not None]
    if not ids_str:
        return 0
    try:
        await r.srem(_DIRTY_KEY, *ids_str)
    except Exception as exc:  # noqa: BLE001
        logger.warning("es_drain_srem_failed", error=str(exc))
    tid_list = []
    for s in ids_str:
        try:
            tid_list.append(int(s))
        except (TypeError, ValueError):
            continue
    if not tid_list:
        return 0
    n = 0
    async with AsyncSessionLocal() as session:
        for tid in tid_list:
            t = await session.get(Track, tid)
            if t and t.is_active and t.is_public:
                await index_track_document(session, t)
                n += 1
        await session.commit()
    if n:
        logger.debug("es_playcount_drain", updated=n)
    return n


async def playcount_drain_loop(stop: asyncio.Event) -> None:
    if not es_available():
        return
    interval = max(
        20.0,
        float(
            settings.elasticsearch_playcount_flush_interval_seconds
        ),
    )
    while not stop.is_set():
        try:
            await _drain_batch()
        except Exception:  # noqa: BLE001
            logger.exception("es_playcount_drain_batch_failed")
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(
                stop.wait(), timeout=interval
            )
