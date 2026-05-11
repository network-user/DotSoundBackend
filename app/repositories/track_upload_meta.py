from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.upload_meta import TrackUploadMeta


class TrackUploadMetaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_track_id(
        self, track_id: int
    ) -> TrackUploadMeta | None:
        result = await self._session.execute(
            select(TrackUploadMeta).where(
                TrackUploadMeta.track_id == track_id
            )
        )
        return result.scalar_one_or_none()
