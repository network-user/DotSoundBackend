from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track_info import TrackInfo


class TrackInfoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_track_id(self, track_id: int) -> TrackInfo | None:
        result = await self._session.execute(
            select(TrackInfo).where(TrackInfo.track_id == track_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        track_id: int,
        *,
        status: str,
        content: str | None,
        fetched_at: datetime | None,
    ) -> TrackInfo:
        row = await self.get_by_track_id(track_id)
        if row is None:
            row = TrackInfo(
                track_id=track_id,
                status=status,
                content=content,
                fetched_at=fetched_at,
            )
            self._session.add(row)
        else:
            row.status = status
            row.content = content
            row.fetched_at = fetched_at
        await self._session.flush()
        return row

    async def set_status(self, track_id: int, status: str) -> None:
        row = await self.get_by_track_id(track_id)
        if row is not None:
            row.status = status
            await self._session.flush()
