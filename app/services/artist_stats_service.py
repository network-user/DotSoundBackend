from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.artist_stats import (
    ArtistStatsRepository,
)
from app.schemas.artist_follow import (
    ArtistListenersResponse,
    MonthlyListenersEntry,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class ArtistStatsService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ArtistStatsRepository(session)

    def _current_ym(self) -> tuple[int, int]:
        now = datetime.now(UTC)
        return now.year, now.month

    def _prev_ym(self) -> tuple[int, int]:
        now = datetime.now(UTC)
        if now.month == 1:
            return now.year - 1, 12
        return now.year, now.month - 1

    async def get_listeners_response(
        self, artist_id: int
    ) -> ArtistListenersResponse:
        year, month = self._current_ym()
        current = await self._repo.count_active_listeners(
            artist_id, year, month
        )
        rows = await self._repo.get_history(artist_id)
        history = [
            MonthlyListenersEntry(
                year=r.year,
                month=r.month,
                unique_listeners=r.unique_listeners,
                total_plays=r.total_plays,
                total_likes=r.total_likes,
                total_followers=r.total_followers,
            )
            for r in rows
        ]
        return ArtistListenersResponse(
            artist_id=artist_id,
            current_month_listeners=current,
            history=history,
        )

    async def snapshot_previous_month(
        self, artist_id: int
    ) -> int:
        year, month = self._prev_ym()
        unique_listeners = await self._repo.count_active_listeners(
            artist_id, year, month
        )
        total_plays = await self._repo.count_total_plays(
            artist_id, year, month
        )
        total_likes = await self._repo.count_total_likes(
            artist_id, year, month
        )
        total_followers = await self._repo.count_total_followers(
            artist_id
        )
        await self._repo.upsert_snapshot(
            artist_id,
            year,
            month,
            unique_listeners,
            total_plays=total_plays,
            total_likes=total_likes,
            total_followers=total_followers,
        )
        return unique_listeners

    async def snapshot_all_artists(self) -> int:
        ids = await self._repo.list_all_artist_ids()
        year, month = self._prev_ym()
        saved = 0
        for artist_id in ids:
            try:
                unique_listeners = (
                    await self._repo.count_active_listeners(
                        artist_id, year, month
                    )
                )
                total_plays = await self._repo.count_total_plays(
                    artist_id, year, month
                )
                total_likes = await self._repo.count_total_likes(
                    artist_id, year, month
                )
                total_followers = (
                    await self._repo.count_total_followers(artist_id)
                )
                await self._repo.upsert_snapshot(
                    artist_id,
                    year,
                    month,
                    unique_listeners,
                    total_plays=total_plays,
                    total_likes=total_likes,
                    total_followers=total_followers,
                )
                saved += 1
            except Exception:
                logger.exception(
                    "artist_stats_snapshot_failed",
                    artist_id=artist_id,
                    year=year,
                    month=month,
                )
        logger.info(
            "artist_stats_snapshot_complete",
            year=year,
            month=month,
            total=saved,
        )
        return saved

    async def get_current_month_listeners(
        self, artist_id: int
    ) -> int:
        year, month = self._current_ym()
        return await self._repo.count_active_listeners(
            artist_id, year, month
        )
