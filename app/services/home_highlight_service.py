"""Home-screen hero "highlight" picker.

Pulls candidates from the existing per-source playlists
(weekly_top, forgotten_treasures, user_top, recent uploads),
forwards them to the PrivateCore policy
(``home_highlight_policy``) and hydrates the verdict into a
public response: a single Track plus a stable ``reason_code``
string that the UI uses to pick the localised "eyebrow" label.

Per-user Redis cache keeps the same hero stable for
``HOME_HIGHLIGHT_TTL_SECONDS`` so that opening Home twice in a
row doesn't shuffle the eyebrow.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.repositories.signal import ListenEventRepository
from app.repositories.track import TrackRepository
from app.services.home_highlight_adapter import (
    HOME_HIGHLIGHT_TTL_SECONDS,
    KIND_FORGOTTEN_TREASURES,
    KIND_PERSONALIZED,
    KIND_WEEKLY_TOP,
    KIND_YOUR_TOP,
    HighlightCandidate,
    pick_home_highlight,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class HomeHighlightService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._track_repo = TrackRepository(session)
        self._listen_repo = ListenEventRepository(session)

    async def get_for_user(
        self, user_id: int
    ) -> dict[str, Any] | None:
        """Return ``{kind, reason_code, track_id, ...}`` or ``None``.

        ``None`` lets the frontend fall back to its existing
        featured-card heuristic (continue / personalized / popular).
        """
        cached = await self._read_cache(user_id)
        if cached is not None:
            return cached

        has_history = await self._has_listen_history(user_id)
        candidates = await self._gather_candidates(
            user_id, has_history=has_history
        )
        if not candidates:
            await self._write_cache(user_id, None)
            return None

        choice = pick_home_highlight(
            candidates,
            viewer_has_listen_history=has_history,
        )
        if choice is None:
            await self._write_cache(user_id, None)
            return None

        track = await self._track_repo.get_by_id(choice.track_id)
        if track is None or not track.is_active:
            return None

        payload: dict[str, Any] = {
            "kind": choice.kind,
            "reason_code": choice.kind,
            "track_id": track.id,
            "title": track.title,
            "artist": track.artist,
            "cover_key": track.cover_key,
            "access_mode": track.access_mode,
            "catalog_type": track.catalog_type,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        await self._write_cache(user_id, payload)
        return payload

    async def _has_listen_history(self, user_id: int) -> bool:
        from app.models.listen_event import ListenEvent

        result = await self._session.execute(
            select(ListenEvent.id)
            .where(ListenEvent.user_id == user_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _gather_candidates(
        self, user_id: int, *, has_history: bool
    ) -> list[HighlightCandidate]:
        out: list[HighlightCandidate] = []

        weekly = await self._weekly_top_candidate()
        if weekly is not None:
            out.append(weekly)

        if has_history:
            personal = await self._user_top_candidate(user_id)
            if personal is not None:
                out.append(personal)

            forgotten = await self._forgotten_candidate(user_id)
            if forgotten is not None:
                out.append(forgotten)

        recent = await self._personalized_candidate(user_id)
        if recent is not None:
            out.append(recent)

        return out

    async def _weekly_top_candidate(
        self,
    ) -> HighlightCandidate | None:
        from app.services.recommendation_service import (
            RecommendationService,
        )

        try:
            svc = RecommendationService(self._session)
            payload = await svc.get_weekly_top_playlist(limit=10)
        except Exception:
            logger.warning(
                "home_highlight_weekly_top_failed",
                exc_info=True,
            )
            return None
        ids = payload.get("track_ids") or []
        if not ids:
            return None
        return HighlightCandidate(
            kind=KIND_WEEKLY_TOP,
            track_id=int(ids[0]),
            score=1.0,
            freshness_days_ago=1,
        )

    async def _user_top_candidate(
        self, user_id: int
    ) -> HighlightCandidate | None:
        from app.services.stats_service import StatsService

        try:
            svc = StatsService(self._session)
            tracks, _window = await svc.get_user_top_tracks(
                user_id, window="30d"
            )
        except Exception:
            logger.warning(
                "home_highlight_user_top_failed",
                user_id=user_id,
                exc_info=True,
            )
            return None
        if not tracks:
            return None
        return HighlightCandidate(
            kind=KIND_YOUR_TOP,
            track_id=int(tracks[0].id),
            score=1.0,
            freshness_days_ago=3,
        )

    async def _forgotten_candidate(
        self, user_id: int
    ) -> HighlightCandidate | None:
        from app.services.recommendation_service import (
            RecommendationService,
        )

        try:
            svc = RecommendationService(self._session)
            payload = await svc.get_forgotten_treasures_playlist(
                user_id, limit=5
            )
        except Exception:
            logger.warning(
                "home_highlight_forgotten_failed",
                user_id=user_id,
                exc_info=True,
            )
            return None
        ids = payload.get("track_ids") or []
        if not ids:
            return None
        return HighlightCandidate(
            kind=KIND_FORGOTTEN_TREASURES,
            track_id=int(ids[0]),
            score=1.0,
            freshness_days_ago=14,
        )

    async def _personalized_candidate(
        self, user_id: int
    ) -> HighlightCandidate | None:
        try:
            tracks, _ = await self._track_repo.list_active(
                offset=0, limit=1, playable_only=True
            )
        except Exception:
            return None
        if not tracks:
            return None
        return HighlightCandidate(
            kind=KIND_PERSONALIZED,
            track_id=int(tracks[0].id),
            score=0.6,
            freshness_days_ago=7,
        )

    @staticmethod
    def _cache_key(user_id: int) -> str:
        return f"rec:home-highlight:{int(user_id)}"

    async def _read_cache(
        self, user_id: int
    ) -> dict[str, Any] | None:
        try:
            redis = get_redis_client()
            raw = await redis.get(self._cache_key(user_id))
        except Exception:
            return None
        if raw is None:
            return None
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if parsed.get("__null__"):
            return None
        return parsed

    async def _write_cache(
        self,
        user_id: int,
        payload: dict[str, Any] | None,
    ) -> None:
        try:
            redis = get_redis_client()
            body = (
                json.dumps({"__null__": True})
                if payload is None
                else json.dumps(payload)
            )
            await redis.set(
                self._cache_key(user_id),
                body,
                ex=HOME_HIGHLIGHT_TTL_SECONDS,
            )
        except Exception:
            logger.debug(
                "home_highlight_cache_write_skipped",
                user_id=user_id,
                exc_info=True,
            )

    @staticmethod
    def freshness_window_seconds() -> int:
        return HOME_HIGHLIGHT_TTL_SECONDS

    @staticmethod
    def reason_code_for_kind(kind: str) -> str:
        """Map kind to a stable reason_code string."""
        return kind

    @staticmethod
    def _placeholder_dt() -> datetime:
        return datetime.now(UTC) - timedelta(days=0)
