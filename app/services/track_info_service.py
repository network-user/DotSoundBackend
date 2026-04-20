"""Track info enrichment service.

Orchestrates fetching AI-generated information about a track.
The actual information provider lives in dotsound_private_core and
is called as an opaque dependency.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.track import Track
from app.models.track_info import TrackInfo
from app.repositories.app_settings import AppSettingsRepository
from app.repositories.track_info import TrackInfoRepository

logger = structlog.get_logger(__name__)

_AI_TRACK_INFO_TTL_KEY = "ai.track_info_ttl_days"
_MAX_CONTENT_CHARS = 12_000
_FETCHING_STALE_SECONDS = 180


class TrackInfoService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_trigger(
        self, track_id: int, force: bool = False
    ) -> TrackInfo:
        """Return cached TrackInfo or enqueue a background fetch if stale/missing."""
        repo = TrackInfoRepository(self._session)
        row = await repo.get_by_track_id(track_id)
        ttl = await self._get_ttl()

        if not force and row and row.status == "done" and row.fetched_at:
            age = (datetime.now(UTC) - row.fetched_at).days
            if age < ttl:
                return row

        if not force and row and row.status == "fetching":
            if row.fetched_at is not None:
                elapsed = (datetime.now(UTC) - row.fetched_at).total_seconds()
                if elapsed < _FETCHING_STALE_SECONDS:
                    return row
            # stale fetching — treat as abandoned, re-enqueue

        row = await repo.upsert(
            track_id,
            status="fetching",
            content=row.content if row else None,
            fetched_at=datetime.now(UTC),
        )
        await self._session.commit()

        try:
            from app.services.track_info_worker import fetch_track_info_task

            await fetch_track_info_task.kiq(track_id=track_id)
        except Exception:
            logger.exception("track_info_enqueue_failed", track_id=track_id)
            await repo.upsert(
                track_id,
                status="failed",
                content=row.content,
                fetched_at=datetime.now(UTC),
            )
            await self._session.commit()

        return row

    async def get(self, track_id: int) -> TrackInfo | None:
        repo = TrackInfoRepository(self._session)
        return await repo.get_by_track_id(track_id)

    async def _get_ttl(self) -> int:
        try:
            settings_repo = AppSettingsRepository(self._session)
            value = await settings_repo.get_value(_AI_TRACK_INFO_TTL_KEY)
            if isinstance(value, dict) and "days" in value:
                days = int(value["days"])
                if days > 0:
                    return days
        except Exception:
            pass
        return settings.track_info_ttl_days


async def _load_track(session: AsyncSession, track_id: int) -> Track | None:
    result = await session.execute(
        select(Track).where(Track.id == track_id)
    )
    return result.scalar_one_or_none()
