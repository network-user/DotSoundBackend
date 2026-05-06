from datetime import UTC, datetime

import structlog
from dotsound_private_core.services.signal_policy import (
    classify_listen,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.signal import (
    ListenEventRepository,
    SearchEventRepository,
)
from app.services.public_playcount_service import (
    PublicPlayCountService,
)

logger = structlog.get_logger(__name__)


class SignalService:
    def __init__(
        self, session: AsyncSession
    ) -> None:
        self._listen_repo = ListenEventRepository(
            session
        )
        self._search_repo = SearchEventRepository(
            session
        )
        self._public_pc = PublicPlayCountService(
            session
        )

    async def record_listen(
        self,
        user_id: int,
        track_id: int,
        duration_listened: int,
        total_duration: int | None,
        source_context: str | None = None,
        last_position: int | None = None,
    ) -> None:
        completed, skipped = classify_listen(
            duration_listened, total_duration
        )

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
            total_duration=total_duration,
        )
        logger.debug(
            "listen_event_recorded",
            user_id=user_id,
            track_id=track_id,
            duration=duration_listened,
            completed=completed,
            skipped=skipped,
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

    async def get_listen_count(
        self, user_id: int
    ) -> int:
        return (
            await self._listen_repo.count_for_user(
                user_id
            )
        )

    async def get_recent_listens(
        self, user_id: int, limit: int = 100
    ) -> list:
        return await self._listen_repo.get_recent(
            user_id, limit
        )
