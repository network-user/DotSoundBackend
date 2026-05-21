from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from dotsound_private_core.services.author_stats_policy import (
    round_display_count,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.repositories.like import LikeRepository
from app.repositories.signal import ListenEventRepository
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class AuthorTrackStats:
    def __init__(
        self,
        track_id: int,
        play_count: int,
        like_count: int,
        listen_events_7d: int,
        listen_events_30d: int,
        play_count_display: int,
        like_count_display: int,
    ) -> None:
        self.track_id = track_id
        self.play_count = play_count
        self.like_count = like_count
        self.listen_events_7d = listen_events_7d
        self.listen_events_30d = listen_events_30d
        self.play_count_display = play_count_display
        self.like_count_display = like_count_display


class AuthorStatsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tracks = TrackRepository(session)
        self._likes = LikeRepository(session)
        self._listen = ListenEventRepository(session)

    async def get_track_stats_for_owner(
        self, track: Track, owner: User
    ) -> AuthorTrackStats:
        if track.uploaded_by_id != owner.id or track.catalog_type != "ugc":
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="not_owner",
            )
        if not track.is_active:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )
        like_n = await self._likes.count_for_track(track.id)
        now = datetime.now(UTC)
        d7 = now - timedelta(days=7)
        d30 = now - timedelta(days=30)
        c7 = await self._listen.count_by_track_since(track.id, d7)
        c30 = await self._listen.count_by_track_since(track.id, d30)
        return AuthorTrackStats(
            track_id=track.id,
            play_count=track.play_count,
            like_count=like_n,
            listen_events_7d=c7,
            listen_events_30d=c30,
            play_count_display=round_display_count(
                int(track.play_count)
            ),
            like_count_display=round_display_count(like_n),
        )
