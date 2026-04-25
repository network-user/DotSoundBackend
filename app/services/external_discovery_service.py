from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.soundcloud_service import SoundCloudService
from dotsound_private_core.services.recommendation_engine import (
    ExternalTrackCandidate,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class ExternalDiscoveryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def discover(
        self,
        preferred_genres: list[str],
        limit_per_source: int = 15,
    ) -> list[ExternalTrackCandidate]:
        """Fetch external track candidates: trending + genre search."""
        if not settings.sc_client_id:
            return []

        svc = SoundCloudService(
            settings.sc_client_id,
            self._session,
        )
        raw: list[dict] = []

        try:
            raw += await svc.get_trending(
                limit=limit_per_source
            )
        except Exception as exc:
            logger.warning(
                "discovery_trending_failed",
                error=str(exc),
            )

        genres_to_search = (preferred_genres or [])[:2] or ["popular", "new"]
        for genre in genres_to_search:
            try:
                raw += await svc.search(
                    genre, limit=limit_per_source
                )
            except Exception as exc:
                logger.warning(
                    "discovery_genre_search_failed",
                    genre=genre,
                    error=str(exc),
                )

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
