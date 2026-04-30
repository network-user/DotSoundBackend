import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.artist_follow import (
    ArtistFollowRepository,
)
from app.repositories.artist import ArtistRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class ArtistFollowService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ArtistFollowRepository(session)
        self._artist_repo = ArtistRepository(session)

    async def toggle_follow(
        self, user_id: int, artist_id: int
    ) -> dict:
        artist = await self._artist_repo.get_by_id(
            artist_id
        )
        if artist is None:
            raise ValueError("artist_not_found")
        following = await self._repo.toggle(
            user_id, artist_id
        )
        follower_count = await self._repo.count_followers(
            artist_id
        )
        logger.info(
            "artist_follow_toggled",
            user_id=user_id,
            artist_id=artist_id,
            following=following,
        )
        return {
            "artist_id": artist_id,
            "following": following,
            "follower_count": follower_count,
        }

    async def get_status(
        self, user_id: int, artist_id: int
    ) -> bool:
        return await self._repo.is_following(
            user_id, artist_id
        )

    async def get_follower_count(
        self, artist_id: int
    ) -> int:
        return await self._repo.count_followers(artist_id)

    async def follow_artists_bulk(
        self, user_id: int, artist_ids: list[int]
    ) -> None:
        for artist_id in artist_ids:
            await self._repo.add(user_id, artist_id)
        if artist_ids:
            logger.info(
                "artist_follow_bulk",
                user_id=user_id,
                count=len(artist_ids),
            )
