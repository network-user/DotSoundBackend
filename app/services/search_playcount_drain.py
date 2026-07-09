from __future__ import annotations

import asyncio
import contextlib

import structlog
from sqlalchemy import select

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.models.track import Track
from app.search.es_client import es_available
from app.services.search_index_service import index_track_document

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)
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
    tid_list = []
    for s in ids_str:
        try:
            tid_list.append(int(s))
        except (TypeError, ValueError):
            continue
    # Index first, drop dirty-set membership only after a successful
    # commit. If the process crashes mid-batch the ids simply stay in
    # the set and get picked up (and re-indexed) on the next drain
    # pass instead of silently losing the signal — re-indexing an
    # already up-to-date track is harmless, so this is safe to repeat.
    n = 0
    if tid_list:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Track).where(Track.id.in_(tid_list))
            )
            tracks_by_id = {t.id: t for t in result.scalars().all()}
            for tid in tid_list:
                t = tracks_by_id.get(tid)
                if t and t.is_active and t.is_public:
                    await index_track_document(session, t)
                    n += 1
            await session.commit()
    try:
        await r.srem(_DIRTY_KEY, *ids_str)
    except Exception as exc:  # noqa: BLE001
        logger.warning("es_drain_srem_failed", error=str(exc))
    if n:
        logger.debug("es_playcount_drain", updated=n)
    return n


async def playcount_drain_loop(stop: asyncio.Event) -> None:
    if not es_available():
        return
    interval = max(
        20.0,
        float(settings.elasticsearch_playcount_flush_interval_seconds),
    )
    while not stop.is_set():
        try:
            await _drain_batch()
        except Exception:  # noqa: BLE001
            logger.exception("es_playcount_drain_batch_failed")
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval)
