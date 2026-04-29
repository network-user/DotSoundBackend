from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.track import TrackRepository
from dotsound_private_core.services.playback_variant_policy import (
    EXTERNAL_SOURCE_PLATFORM_ORDER,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_REDIS_BLOCK_TTL = 3600
_BLOCK_PREFIX = "fallback:block:"


class TrackFallbackService:
    def __init__(
        self, session: AsyncSession, settings: object
    ) -> None:
        self._session = session
        self._settings = settings

    async def find_playback_replacement(
        self, track: Track
    ) -> Track | None:
        if track.duration_seconds is None or not track.title:
            return None

        from app.core.redis import get_redis_client

        redis = get_redis_client()
        block_key = f"{_BLOCK_PREFIX}{track.id}"
        if await redis.get(block_key):
            logger.debug(
                "track_fallback_blocked_by_cache",
                track_id=track.id,
            )
            return None

        current_platform = (track.source_platform or "").strip().lower()
        platforms_to_try = [
            p for p in EXTERNAL_SOURCE_PLATFORM_ORDER if p != current_platform
        ]

        repo = TrackRepository(self._session)
        for platform in platforms_to_try:
            candidates = await repo.find_by_title_and_duration(
                title=track.title,
                duration_seconds=track.duration_seconds,
                platform=platform,
            )
            if candidates:
                replacement = candidates[0]
                logger.info(
                    "track_fallback_candidate",
                    track_id=track.id,
                    old_platform=current_platform,
                    new_platform=platform,
                    replacement_id=replacement.id,
                )
                return replacement

        await redis.set(block_key, "not_found", ex=_REDIS_BLOCK_TTL)
        logger.info(
            "track_fallback_not_found",
            track_id=track.id,
            tried=platforms_to_try,
        )
        return None

    async def find_and_apply_fallback(
        self, track: Track
    ) -> Track | None:
        """Return a replacement track for playback without mutating ``track``.

        Legacy name kept for callers; rows are no longer rewritten in-place.
        """
        return await self.find_playback_replacement(track)
