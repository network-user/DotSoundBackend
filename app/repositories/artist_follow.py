from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist_follow import ArtistFollow


class ArtistFollowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_following(
        self, user_id: int, artist_id: int
    ) -> bool:
        result = await self._session.execute(
            select(ArtistFollow).where(
                ArtistFollow.user_id == user_id,
                ArtistFollow.artist_id == artist_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def add(
        self, user_id: int, artist_id: int
    ) -> None:
        if await self.is_following(user_id, artist_id):
            return
        self._session.add(
            ArtistFollow(
                user_id=user_id,
                artist_id=artist_id,
            )
        )
        await self._session.flush()

    async def remove(
        self, user_id: int, artist_id: int
    ) -> None:
        await self._session.execute(
            delete(ArtistFollow).where(
                ArtistFollow.user_id == user_id,
                ArtistFollow.artist_id == artist_id,
            )
        )

    async def toggle(
        self, user_id: int, artist_id: int
    ) -> bool:
        existing = await self.is_following(
            user_id, artist_id
        )
        if existing:
            await self.remove(user_id, artist_id)
            return False
        await self.add(user_id, artist_id)
        return True

    async def count_followers(
        self, artist_id: int
    ) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(ArtistFollow)
            .where(
                ArtistFollow.artist_id == artist_id
            )
        )
        return result.scalar_one() or 0

    async def list_followed_artist_ids(
        self, user_id: int
    ) -> list[int]:
        result = await self._session.execute(
            select(ArtistFollow.artist_id).where(
                ArtistFollow.user_id == user_id
            )
        )
        return list(result.scalars().all())
