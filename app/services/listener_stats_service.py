from __future__ import annotations

from collections import defaultdict

import structlog
from dotsound_private_core.services.listener_stats_policy import (
    credited_listen_seconds,
    is_allowed_period_days,
    listener_stats_since_utc,
    topic_qualifies_as_top,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.signal import ListenEventRepository

logger = structlog.get_logger(__name__)


class ListenerStatsService:
    """Compute personal listening aggregates for the authenticated
    user (minutes listened, top artist, top genre). Decision rules
    live in PrivateCore (`listener_stats_policy`); we own only the
    transport.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._listen_repo = ListenEventRepository(session)

    async def get_listener_stats(
        self,
        user_id: int,
        period_days: int,
    ) -> dict:
        if not is_allowed_period_days(period_days):
            period_days = 30
        since = listener_stats_since_utc(period_days)

        rows = await self._listen_repo.get_user_listen_rows_since(
            user_id=user_id, since=since
        )
        if not rows:
            return {
                "period_days": period_days,
                "minutes_listened": 0,
                "tracks_listened": 0,
                "top_artists": [],
                "top_genres": [],
            }

        track_ids = list({tid for tid, _, _ in rows})
        track_rows = (
            await self._session.execute(
                select(
                    Track.id, Track.artist, Track.genre
                ).where(Track.id.in_(track_ids))
            )
        ).all()
        track_meta: dict[int, tuple[str | None, str | None]] = {
            int(r[0]): (r[1], r[2]) for r in track_rows
        }

        total_seconds = 0
        unique_tracks: set[int] = set()
        artist_seconds: dict[str, int] = defaultdict(int)
        artist_plays: dict[str, int] = defaultdict(int)
        genre_seconds: dict[str, int] = defaultdict(int)
        genre_plays: dict[str, int] = defaultdict(int)

        for track_id, dur, total in rows:
            credited = credited_listen_seconds(
                duration_listened=dur,
                total_duration=total,
            )
            if credited <= 0:
                continue
            total_seconds += credited
            unique_tracks.add(track_id)
            artist, genre = track_meta.get(track_id, (None, None))
            if artist:
                key = artist.strip()
                if key:
                    artist_seconds[key] += credited
                    artist_plays[key] += 1
            if genre:
                key_g = genre.strip()
                if key_g:
                    genre_seconds[key_g] += credited
                    genre_plays[key_g] += 1

        def _top(seconds: dict[str, int], plays: dict[str, int]) -> list[dict]:
            ranked = sorted(
                seconds.items(),
                key=lambda kv: (kv[1], plays.get(kv[0], 0)),
                reverse=True,
            )
            out: list[dict] = []
            for name, secs in ranked[:5]:
                if not topic_qualifies_as_top(
                    plays.get(name, 0),
                    period_days=period_days,
                ):
                    continue
                out.append(
                    {
                        "name": name,
                        "minutes": int(secs // 60),
                        "plays": int(plays.get(name, 0)),
                    }
                )
            return out

        return {
            "period_days": period_days,
            "minutes_listened": int(total_seconds // 60),
            "tracks_listened": len(unique_tracks),
            "top_artists": _top(artist_seconds, artist_plays),
            "top_genres": _top(genre_seconds, genre_plays),
        }
