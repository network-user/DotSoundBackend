import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dislike import Dislike
from app.repositories.base import BaseRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class DislikeRepository(BaseRepository[Dislike]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Dislike)

    async def get(
        self, user_id: int, track_id: int
    ) -> Dislike | None:
        result = await self._session.execute(
            select(Dislike).where(
                Dislike.user_id == user_id,
                Dislike.track_id == track_id,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, user_id: int, track_id: int) -> Dislike:
        return await self.create(
            user_id=user_id, track_id=track_id
        )

    async def remove(self, user_id: int, track_id: int) -> bool:
        result = await self._session.execute(
            delete(Dislike).where(
                Dislike.user_id == user_id,
                Dislike.track_id == track_id,
            )
        )
        await self._session.flush()
        return result.rowcount > 0
