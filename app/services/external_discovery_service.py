from __future__ import annotations

import asyncio

import structlog
from dotsound_private_core.services.recommendation_engine import (
    ExternalTrackCandidate,
)
from dotsound_private_core.services.recommendation_language_policy import (
    should_boost_russian_discovery,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.soundcloud_service import SoundCloudService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

_DISCOVER_TIMEOUT_SECONDS = 8


class ExternalDiscoveryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def discover(
        self,
        preferred_genres: list[str],
        limit_per_source: int = 15,
        language_affinity: dict[str, float] | None = None,
        user_locale: str | None = None,
    ) -> list[ExternalTrackCandidate]:
        """Fetch external track candidates: trending + genre search."""
        if not settings.sc_client_id:
            return []

        svc = SoundCloudService(
            settings.sc_client_id,
            self._session,
        )

        genres_to_search = (preferred_genres or [])[:2] or [
            "popular",
            "new",
        ]
        queries: list[str] = ["__trending__"] + list(genres_to_search)
        if should_boost_russian_discovery(language_affinity, user_locale):
            queries += ["russian", "russian hip hop", "russian pop"]

        async def _fetch(term: str) -> list[dict]:
            try:
                if term == "__trending__":
                    return await svc.get_trending(limit=limit_per_source)
                return await svc.search(term, limit=limit_per_source)
            except Exception as exc:
                label = (
                    "discovery_trending_failed"
                    if term == "__trending__"
                    else "discovery_search_failed"
                )
                logger.warning(label, term=term, error=str(exc))
                return []

        results = await asyncio.gather(*[_fetch(q) for q in queries])
        raw: list[dict] = [item for batch in results for item in batch]

        seen: set[str] = set()
        candidates: list[ExternalTrackCandidate] = []
        for item in raw:
            eid = str(item.get("id", ""))
            if not eid or eid in seen:
                continue
            seen.add(eid)
            duration_ms = item.get("duration")
            candidates.append(
                ExternalTrackCandidate(
                    title=item.get("title", ""),
                    artist=(
                        (item.get("user") or {}).get(
                            "username"
                        )
                    ),
                    source="soundcloud",
                    external_url=item.get(
                        "permalink_url"
                    ),
                    external_id=eid,
                    genre=item.get("genre"),
                    cover_url=item.get("artwork_url"),
                    play_count=item.get(
                        "playback_count", 0
                    )
                    or 0,
                    duration_seconds=(
                        int(duration_ms) // 1000
                        if duration_ms
                        else None
                    ),
                )
            )

        logger.info(
            "discovery_done",
            total=len(candidates),
        )
        return candidates
