"""Recommendation impression telemetry.

Single point that backend goes through to log "this list of tracks
was surfaced to this user on this surface". Each call generates a
unique ``recommendation_id`` so a downstream ``ListenEvent`` can
join back to the impression.

The ``algorithm_version`` is opaque to backend — it comes from
``dotsound_private_core`` and is stored as-is. Backend never
interprets it.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recommendation_impression import (
    RecommendationImpression,
)
from dotsound_private_core.services.recommendation_engine import (
    get_algorithm_version,
)

logger = structlog.get_logger(__name__)


class RecsysTelemetryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_impressions(
        self,
        *,
        user_id: int,
        surface: str,
        track_ids: list[int],
        algorithm_version: str | None = None,
    ) -> str:
        """Record an impression batch and return its recommendation_id.

        ``surface`` examples: ``daily_mix``, ``weekly_mix``,
        ``radio``, ``for_you``, ``similar``.
        """
        if not track_ids:
            return ""
        rec_id = uuid.uuid4().hex
        version = (
            algorithm_version
            or get_algorithm_version()
        )
        rows = [
            RecommendationImpression(
                user_id=user_id,
                track_id=tid,
                surface=surface,
                algorithm_version=version,
                position=pos,
                recommendation_id=rec_id,
            )
            for pos, tid in enumerate(track_ids)
        ]
        self._session.add_all(rows)
        await self._session.flush()
        logger.info(
            "recsys_metric",
            event="impression_batch",
            user_id=user_id,
            surface=surface,
            algorithm_version=version,
            recommendation_id=rec_id,
            count=len(track_ids),
        )
        return rec_id
