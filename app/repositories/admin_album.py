from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.album import Album
from app.models.track import Track


class AdminAlbumRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_albums(
        self,
        *,
        page: int,
        size: int,
        search: str | None,
    ) -> tuple[list[tuple[Album, int]], int]:
        tc = (
            select(func.count(Track.id))
            .where(Track.album_id == Album.id)
            .scalar_subquery()
        )
        base = select(Album, tc)
        count_q = select(func.count(Album.id))
        if search:
            pattern = f"%{search}%"
            cond = Album.title.ilike(pattern)
            base = base.where(cond)
            count_q = count_q.where(cond)
        total_r = await self._session.execute(count_q)
        total = int(total_r.scalar_one())
        base = (
            base.order_by(Album.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self._session.execute(base)
        rows = list(result.all())
        return rows, total

    async def get_with_tracks(self, album_id: int) -> Album | None:
        result = await self._session.execute(
            select(Album)
            .options(selectinload(Album.tracks))
            .where(Album.id == album_id)
        )
        return result.scalar_one_or_none()
