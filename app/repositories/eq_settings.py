from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eq_settings import UserEqSettings
from app.repositories.base import BaseRepository


class EqSettingsRepository(
    BaseRepository[UserEqSettings]
):
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        super().__init__(session, UserEqSettings)

    async def get_by_user_id(
        self,
        user_id: int,
    ) -> UserEqSettings | None:
        result = await self._session.execute(
            select(UserEqSettings).where(
                UserEqSettings.user_id == user_id
            )
        )
        return result.scalar_one_or_none()
