from __future__ import annotations

import structlog
from dotsound_private_core.services.playback_variant_policy import (
    EXTERNAL_SOURCE_PLATFORM_ORDER,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_REDIS_BLOCK_TTL = 3600
_BLOCK_PREFIX = "fallback:block:"
_SC_REFRESH_PREFIX = "sc_refresh:no_match:"
_SC_REFRESH_NO_MATCH_TTL = 86400
_SC_REFRESH_SAME_URL_TTL = 3600


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

    async def try_refresh_sc_url(self, track: Track) -> bool:
        if not track.title:
            return False

        from app.core.redis import get_redis_client
        from app.services.soundcloud_service import (
            SoundCloudService,
        )

        redis = get_redis_client()
        no_match_key = f"{_SC_REFRESH_PREFIX}{track.id}"
        if await redis.get(no_match_key):
            return False

        sc_svc = SoundCloudService(
            getattr(self._settings, "sc_client_id", "") or "",
            self._session,
        )
        best = await sc_svc.search_best_match(
            title=track.title,
            artist=track.artist or None,
            duration_seconds=track.duration_seconds,
        )

        if not best:
            await redis.set(
                no_match_key,
                "1",
                ex=_SC_REFRESH_NO_MATCH_TTL,
            )
            logger.info(
                "sc_url_refresh_no_match",
                track_id=track.id,
            )
            return False

        new_url: str | None = best.get("permalink_url")
        if not new_url:
            await redis.set(
                no_match_key,
                "1",
                ex=_SC_REFRESH_NO_MATCH_TTL,
            )
            return False

        if new_url == track.sc_url:
            await redis.set(
                no_match_key,
                "1",
                ex=_SC_REFRESH_SAME_URL_TTL,
            )
            logger.info(
                "sc_url_refresh_same_url",
                track_id=track.id,
            )
            return False

        new_ext_id: str | None = (
            str(best["id"]) if best.get("id") else None
        )
        repo = TrackRepository(self._session)
        await repo.update_sc_url(track.id, new_url, new_ext_id)
        track.sc_url = new_url
        if new_ext_id is not None:
            track.external_id = new_ext_id

        logger.info(
            "sc_url_refreshed",
            track_id=track.id,
            new_url=new_url,
        )
        return True

    async def find_and_apply_fallback(
        self, track: Track
    ) -> Track | None:
        """Return a replacement track for playback without mutating ``track``.

        Legacy name kept for callers; rows are no longer rewritten in-place.
        """
        return await self.find_playback_replacement(track)
