from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_preference import UserPreference
from app.repositories.base import BaseRepository


class PreferenceRepository(
    BaseRepository[UserPreference]
):
    def __init__(
        self, session: AsyncSession
    ) -> None:
        super().__init__(session, UserPreference)

    async def get_by_user_id(
        self, user_id: int
    ) -> UserPreference | None:
        result = await self._session.execute(
            select(UserPreference).where(
                UserPreference.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        user_id: int,
        **kwargs: object,
    ) -> UserPreference:
        existing = await self.get_by_user_id(
            user_id
        )
        if existing:
            for k, v in kwargs.items():
                setattr(existing, k, v)
            await self._session.flush()
            await self._session.refresh(existing)
            return existing
        return await self.create(
            user_id=user_id, **kwargs
        )
