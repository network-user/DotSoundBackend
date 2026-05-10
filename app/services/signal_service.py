from datetime import UTC, datetime

import structlog
from dotsound_private_core.services.signal_policy import (
    classify_listen,
    classify_listen_outcome,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import (
    recsys_impression_position_observed,
    recsys_listen_outcome_observed,
)
from app.repositories.signal import (
    ListenEventRepository,
    SearchEventRepository,
)
from app.services.public_playcount_service import (
    PublicPlayCountService,
)
from app.services.recsys_telemetry import (
    RecsysTelemetryService,
)

logger = structlog.get_logger(__name__)

_FALLBACK_SURFACE_LABEL = "unknown"


class SignalService:
    def __init__(self, session: AsyncSession) -> None:
        self._listen_repo = ListenEventRepository(session)
        self._search_repo = SearchEventRepository(session)
        self._public_pc = PublicPlayCountService(session)
        self._telemetry = RecsysTelemetryService(session)

    async def record_listen(
        self,
        user_id: int,
        track_id: int,
        duration_listened: int,
        total_duration: int | None,
        source_context: str | None = None,
        last_position: int | None = None,
    ) -> None:
        completed, skipped = classify_listen(duration_listened, total_duration)

        await self._listen_repo.create_event(
            user_id=user_id,
            track_id=track_id,
            started_at=datetime.now(UTC),
            duration_listened=duration_listened,
            total_duration=total_duration,
            completed=completed,
            skipped=skipped,
            source_context=source_context,
            last_position=last_position,
        )
        await self._public_pc.bump_after_qualified_listen(
            user_id=user_id,
            track_id=track_id,
            completed=completed,
            skipped=skipped,
            duration_listened=duration_listened,
        )
        await self._observe_recsys_outcome(
            user_id=user_id,
            track_id=track_id,
            duration_listened=duration_listened,
            total_duration=total_duration,
            completed=completed,
            skipped=skipped,
            source_context=source_context,
        )
        logger.debug(
            "listen_event_recorded",
            user_id=user_id,
            track_id=track_id,
            duration=duration_listened,
            completed=completed,
            skipped=skipped,
        )

    async def _observe_recsys_outcome(
        self,
        *,
        user_id: int,
        track_id: int,
        duration_listened: int,
        total_duration: int | None,
        completed: bool,
        skipped: bool,
        source_context: str | None,
    ) -> None:
        outcome = classify_listen_outcome(
            float(duration_listened),
            float(total_duration) if total_duration else None,
            completed=completed,
            skipped=skipped,
        )
        impression = await self._telemetry.find_recent_impression_for_listen(
            user_id=user_id,
            track_id=track_id,
        )
        if impression is not None:
            surface, position = impression
            recsys_listen_outcome_observed(surface=surface, outcome=outcome)
            if outcome == "completed":
                recsys_impression_position_observed(
                    surface=surface, position=position + 1
                )
            return
        fallback_surface = source_context or _FALLBACK_SURFACE_LABEL
        recsys_listen_outcome_observed(
            surface=fallback_surface, outcome=outcome
        )

    async def record_search_click(
        self,
        user_id: int,
        query: str,
        results_count: int = 0,
        clicked_track_id: int | None = None,
    ) -> None:
        await self._search_repo.create_event(
            user_id=user_id,
            query=query,
            results_count=results_count,
            clicked_track_id=clicked_track_id,
        )
        logger.debug(
            "search_event_recorded",
            user_id=user_id,
            query=query,
            clicked=clicked_track_id,
        )

    async def get_listen_count(self, user_id: int) -> int:
        return await self._listen_repo.count_for_user(user_id)

    async def get_recent_listens(self, user_id: int, limit: int = 100) -> list:
        return await self._listen_repo.get_recent(user_id, limit)
