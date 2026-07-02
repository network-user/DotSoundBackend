"""Fire-and-forget stream URL warming for upcoming tracks.

Warms the Redis URL cache so the next play request finds a cached
URL instead of re-calling the external provider API. The hot path
in the player is ``GET /api/v1/tracks/{id}/stream`` -> resolver ->
provider HTTP call (300 ms - 8 s on a cold miss). By warming the
URL cache for the next N tracks the moment we hand the user the
current track, we cut that resolver call out of the user-perceived
startup latency entirely.

Resolution is concurrent: a single user-facing prefetch call covers
3-5 upcoming tracks, and serialising the resolver round-trips would
defeat the point. We cap concurrency to a small number so a queue
spike does not detonate the provider's rate-limiter.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from app.core.db import AsyncSessionLocal
from app.models.track import Track

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_DEFAULT_PARALLELISM = 4


async def _warm_one(
    session: AsyncSession,
    track_id: int,
    semaphore: asyncio.Semaphore,
) -> None:
    from app.api.v1.tracks.playback import _resolve_third_party_stream

    async with semaphore:
        track = await session.get(Track, track_id)
        if track is None:
            return
        if track.access_mode != "third_party_stream":
            return
        if track.blob_id is not None:
            return
        try:
            await _resolve_third_party_stream(
                track,
                session,
                use_cache=True,
            )
        except Exception as exc:  # noqa: BLE001 — best-effort warmer
            logger.debug(
                "prefetch_url_miss",
                track_id=track_id,
                error=str(exc),
            )


async def prefetch_track_urls(
    track_ids: list[int],
    *,
    parallelism: int = _DEFAULT_PARALLELISM,
) -> None:
    """Warm provider URL caches for ``track_ids`` in parallel.

    A bounded semaphore keeps concurrent provider requests within
    safe limits even when a long radio queue arrives at once. The
    caller is fire-and-forget; per-track failures only log at debug.
    """
    if not track_ids:
        return
    # Жёсткий потолок 16 -> 4: префетч - фоновый разогрев, ему некуда
    # спешить, а каждый слот держит provider-ответы в памяти.
    bound = max(1, min(int(parallelism), 4))
    semaphore = asyncio.Semaphore(bound)
    async with AsyncSessionLocal() as session:
        await asyncio.gather(
            *(_warm_one(session, tid, semaphore) for tid in track_ids),
            return_exceptions=False,
        )
