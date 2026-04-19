from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist_supplemental_info import ArtistSupplementalInfo


class ArtistSupplementalInfoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_artist_id(
        self, artist_id: int
    ) -> ArtistSupplementalInfo | None:
        result = await self._session.execute(
            select(ArtistSupplementalInfo).where(
                ArtistSupplementalInfo.artist_id == artist_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        artist_id: int,
        *,
        status: str,
        content: str | None,
        fetched_at: datetime | None,
    ) -> ArtistSupplementalInfo:
        row = await self.get_by_artist_id(artist_id)
        if row is None:
            row = ArtistSupplementalInfo(
                artist_id=artist_id,
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

    async def set_status(self, artist_id: int, status: str) -> None:
        row = await self.get_by_artist_id(artist_id)
        if row is not None:
            row.status = status
            await self._session.flush()
