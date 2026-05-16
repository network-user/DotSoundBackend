from __future__ import annotations

import re
from typing import Any

import structlog
from dotsound_private_core.services.playback_variant_policy import (
    EXTERNAL_SOURCE_PLATFORM_ORDER,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_REDIS_BLOCK_TTL = 3600
_BLOCK_PREFIX = "fallback:block:"
_SC_REFRESH_PREFIX = "sc_refresh:no_match:"
_SC_REFRESH_NO_MATCH_TTL = 86400
_SC_REFRESH_SAME_URL_TTL = 3600
_TITLE_WORD_RE = re.compile(r"[a-zA-Zа-яА-Я0-9]+")


def _update_refresh_diagnostics(
    diagnostics: dict[str, Any] | None,
    **values: object,
) -> None:
    if diagnostics is None:
        return
    diagnostics.update(values)


class TrackFallbackService:
    def __init__(self, session: AsyncSession, settings: object) -> None:
        self._session = session
        self._settings = settings

    async def find_playback_replacement(self, track: Track) -> Track | None:
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
            relaxed = await repo.find_by_similar_title(
                platform=platform,
                title_queries=self._title_queries(track.title),
                duration_seconds=track.duration_seconds,
                duration_window_sec=45,
                limit=5,
            )
            if relaxed:
                replacement = relaxed[0]
                logger.info(
                    "track_fallback_candidate_relaxed",
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

    @staticmethod
    def _title_queries(title: str) -> list[str]:
        normalized = " ".join(_TITLE_WORD_RE.findall(title.lower()))
        if not normalized:
            return []
        tokens = [t for t in normalized.split() if len(t) >= 3]
        if not tokens:
            return [normalized]
        full = " ".join(tokens)
        out: list[str] = [full]
        out.extend(tokens[:3])
        seen: set[str] = set()
        dedup: list[str] = []
        for item in out:
            if item and item not in seen:
                seen.add(item)
                dedup.append(item)
        return dedup

    async def try_refresh_sc_url(
        self,
        track: Track,
        *,
        use_no_match_cache: bool = True,
        diagnostics: dict[str, Any] | None = None,
    ) -> bool:
        if not track.title:
            _update_refresh_diagnostics(
                diagnostics,
                candidate_found=False,
                rejected_reason="missing_title",
            )
            return False

        from app.core.redis import get_redis_client
        from app.services.soundcloud_service import (
            SoundCloudService,
        )

        redis = get_redis_client()
        no_match_key = f"{_SC_REFRESH_PREFIX}{track.id}"
        if use_no_match_cache and await redis.get(no_match_key):
            _update_refresh_diagnostics(
                diagnostics,
                cache="hit",
                candidate_found=False,
                rejected_reason="no_match_cache_hit",
            )
            return False
        _update_refresh_diagnostics(
            diagnostics,
            cache="miss" if use_no_match_cache else "bypassed",
        )

        sc_svc = SoundCloudService(
            getattr(self._settings, "sc_client_id", "") or "",
            self._session,
        )
        try:
            best = await sc_svc.search_best_match(
                title=track.title,
                artist=track.artist or None,
                duration_seconds=track.duration_seconds,
            )
        except Exception as exc:
            _update_refresh_diagnostics(
                diagnostics,
                candidate_found=False,
                rejected_reason="search_failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise

        if not best:
            _update_refresh_diagnostics(
                diagnostics,
                candidate_found=False,
                rejected_reason="no_candidate",
            )
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
        new_ext_id: str | None = str(best["id"]) if best.get("id") else None
        _update_refresh_diagnostics(
            diagnostics,
            candidate_found=True,
            candidate_url=new_url,
            candidate_external_id=new_ext_id,
            candidate_title=best.get("title"),
        )
        if not new_url:
            _update_refresh_diagnostics(
                diagnostics,
                rejected_reason="candidate_missing_permalink",
            )
            await redis.set(
                no_match_key,
                "1",
                ex=_SC_REFRESH_NO_MATCH_TTL,
            )
            return False

        if new_url == track.sc_url:
            _update_refresh_diagnostics(
                diagnostics,
                rejected_reason="same_url",
            )
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

        repo = TrackRepository(self._session)
        url_owner = await repo.get_track_id_by_sc_url(new_url)
        if url_owner is not None:
            _update_refresh_diagnostics(
                diagnostics,
                rejected_reason="candidate_url_taken",
                conflict_track_id=url_owner,
            )
            await redis.set(
                no_match_key,
                "1",
                ex=_SC_REFRESH_NO_MATCH_TTL,
            )
            logger.info(
                "sc_url_refresh_url_taken",
                track_id=track.id,
                conflict_track_id=url_owner,
            )
            return False
        if (
            new_ext_id is not None
            and track.imported_from
            and await repo.other_track_has_imported_external(
                imported_from=track.imported_from,
                external_id=new_ext_id,
                exclude_track_id=track.id,
            )
        ):
            _update_refresh_diagnostics(
                diagnostics,
                rejected_reason="candidate_external_id_taken",
            )
            await redis.set(
                no_match_key,
                "1",
                ex=_SC_REFRESH_NO_MATCH_TTL,
            )
            logger.info(
                "sc_url_refresh_external_id_taken",
                track_id=track.id,
                external_id=new_ext_id,
            )
            return False
        try:
            await repo.update_sc_url(track.id, new_url, new_ext_id)
        except IntegrityError:
            await self._session.rollback()
            _update_refresh_diagnostics(
                diagnostics,
                rejected_reason="integrity_error",
            )
            await redis.set(
                no_match_key,
                "1",
                ex=_SC_REFRESH_NO_MATCH_TTL,
            )
            logger.warning(
                "sc_url_refresh_integrity_error",
                track_id=track.id,
            )
            return False
        track.sc_url = new_url
        track.source_url = new_url
        track.canonical_source_url = new_url
        if new_ext_id is not None:
            track.external_id = new_ext_id

        logger.info(
            "sc_url_refreshed",
            track_id=track.id,
            new_url=new_url,
        )
        _update_refresh_diagnostics(
            diagnostics,
            refreshed=True,
            rejected_reason=None,
            new_url=new_url,
        )
        return True

    async def find_and_apply_fallback(self, track: Track) -> Track | None:
        """Return a replacement track for playback without mutating ``track``.

        Legacy name kept for callers; rows are no longer rewritten in-place.
        """
        return await self.find_playback_replacement(track)
