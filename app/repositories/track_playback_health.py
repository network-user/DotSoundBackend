from __future__ import annotations

from datetime import UTC, datetime, timedelta

from dotsound_private_core.services.playback_health_policy import (
    PLAYBACK_HEALTH_AUTO_SUPPRESS_DURATION,
    PLAYBACK_HEALTH_ROLLING_WINDOW_HOURS,
    should_auto_suppress_from_server_signals,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.track_playback_failure_event import (
    TrackPlaybackFailureEvent,
)

SERVER_SOURCES_FOR_SUPPRESSION_THRESH = frozenset(
    {
        "server_recovery_exhausted",
        "server_proxy_upstream",
    },
)


class TrackPlaybackHealthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_failure_event(
        self,
        *,
        track_id: int,
        user_id: int | None,
        source: str,
        http_status: int | None,
        detail_truncated: str | None,
    ) -> TrackPlaybackFailureEvent:
        row = TrackPlaybackFailureEvent(
            track_id=track_id,
            user_id=user_id,
            source=source,
            http_status=http_status,
            detail_truncated=detail_truncated,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def count_server_failure_events_since(
        self,
        *,
        track_id: int,
        since: datetime,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(TrackPlaybackFailureEvent)
            .where(
                TrackPlaybackFailureEvent.track_id == track_id,
                TrackPlaybackFailureEvent.created_at >= since,
                TrackPlaybackFailureEvent.source.in_(
                    SERVER_SOURCES_FOR_SUPPRESSION_THRESH,
                ),
            )
        )
        res = await self._session.execute(stmt)
        return int(res.scalar_one())

    async def count_distinct_authenticated_users_since(
        self,
        *,
        track_id: int,
        since: datetime,
    ) -> int:
        stmt = (
            select(
                func.count(func.distinct(TrackPlaybackFailureEvent.user_id))
            )
            .select_from(TrackPlaybackFailureEvent)
            .where(
                TrackPlaybackFailureEvent.track_id == track_id,
                TrackPlaybackFailureEvent.created_at >= since,
                TrackPlaybackFailureEvent.user_id.isnot(None),
                TrackPlaybackFailureEvent.source.in_(
                    SERVER_SOURCES_FOR_SUPPRESSION_THRESH,
                ),
            )
        )
        res = await self._session.execute(stmt)
        return int(res.scalar_one())

    async def maybe_apply_auto_suppression(
        self,
        *,
        track_id: int,
    ) -> Track | None:
        since = datetime.now(UTC) - timedelta(
            hours=PLAYBACK_HEALTH_ROLLING_WINDOW_HOURS,
        )
        srv_total = (
            await self.count_server_failure_events_since(
                track_id=track_id,
                since=since,
            )
        )
        distinct_users = (
            await self.count_distinct_authenticated_users_since(
                track_id=track_id,
                since=since,
            )
        )
        if not should_auto_suppress_from_server_signals(
            distinct_authenticated_users=distinct_users,
            server_failure_events_in_window=srv_total,
        ):
            return None

        stmt = select(Track).where(Track.id == track_id)
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            return None
        until_ts = datetime.now(UTC) + PLAYBACK_HEALTH_AUTO_SUPPRESS_DURATION
        row.playback_suppressed_until = until_ts
        await self._session.flush()
        return row
