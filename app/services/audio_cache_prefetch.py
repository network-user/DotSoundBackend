"""Fire-and-forget stream URL warming for upcoming tracks.

Warms the Redis URL cache so the next play request finds a cached
URL instead of re-calling the external provider API.
"""

from __future__ import annotations

import structlog

from app.core.db import AsyncSessionLocal
from app.models.track import Track

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def prefetch_track_urls(track_ids: list[int]) -> None:
    from app.api.v1.tracks.playback import _resolve_third_party_stream

    async with AsyncSessionLocal() as session:
        for track_id in track_ids:
            track = await session.get(Track, track_id)
            if track is None:
                continue
            if track.access_mode != "third_party_stream":
                continue
            if track.blob_id is not None:
                # Already cached in S3 — no URL to warm
                continue
            try:
                await _resolve_third_party_stream(track, session, use_cache=True)
            except Exception as exc:
                logger.debug(
                    "prefetch_url_miss",
                    track_id=track_id,
                    error=str(exc),
                )
