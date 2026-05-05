from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.genre_mix_override import GenreMixOverride


class GenreMixOverrideRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_genres(
        self,
        genres: list[str],
    ) -> list[GenreMixOverride]:
        if not genres:
            return []
        result = await self._session.execute(
            select(GenreMixOverride).where(
                GenreMixOverride.genre.in_(genres),
            )
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        genre: str,
        title: str,
        track_ids: list[int],
        updated_by_id: int | None,
    ) -> GenreMixOverride:
        result = await self._session.execute(
            select(GenreMixOverride).where(
                GenreMixOverride.genre == genre,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = GenreMixOverride(
                genre=genre,
                title=title,
                track_ids=track_ids,
                updated_by_id=updated_by_id,
            )
            self._session.add(row)
        else:
            row.title = title
            row.track_ids = track_ids
            row.updated_by_id = updated_by_id
        await self._session.flush()
        await self._session.refresh(row)
        return row
