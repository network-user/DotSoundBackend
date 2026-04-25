from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_PLATFORM_PRIORITY = ("youtube", "soundcloud", "bandcamp")
_REDIS_BLOCK_TTL = 3600
_BLOCK_PREFIX = "fallback:block:"


class TrackFallbackService:
    def __init__(
        self, session: AsyncSession, settings: object
    ) -> None:
        self._session = session
        self._settings = settings

    async def find_and_apply_fallback(
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

        current_platform = track.source_platform or ""
        platforms_to_try = [
            p for p in _PLATFORM_PRIORITY if p != current_platform
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
                await self._apply_replacement(track, replacement)
                logger.info(
                    "track_fallback_applied",
                    track_id=track.id,
                    old_platform=current_platform,
                    new_platform=platform,
                    replacement_id=replacement.id,
                )
                return track

        await redis.set(block_key, "not_found", ex=_REDIS_BLOCK_TTL)
        logger.info(
            "track_fallback_not_found",
            track_id=track.id,
            tried=platforms_to_try,
        )
        return None

    async def _apply_replacement(
        self, track: Track, source: Track
    ) -> None:
        track.previous_source_url = track.source_url
        track.source_url = source.source_url
        track.source_platform = source.source_platform
        track.external_id = source.external_id
        track.canonical_source_url = source.canonical_source_url
        track.sc_url = None
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(track)
