import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserRepository(session)

    async def register_or_update(
        self, data: UserCreate
    ) -> tuple[User, bool]:
        user, created = await self._repo.upsert(
            telegram_id=data.telegram_id,
            username=data.username,
            first_name=data.first_name,
            last_name=data.last_name,
        )
        logger.info(
            "user_upserted",
            telegram_id=data.telegram_id,
            created=created,
            user_id=user.id,
        )
        return user, created

    async def get_by_id(self, user_id: int) -> User | None:
        user = await self._repo.get_by_id(user_id)
        if not user:
            # Fallback to telegram_id if not found by primary key
            user = await self._repo.get_by_telegram_id(user_id)
        
        if not user:
            logger.warning("user_not_found", user_id=user_id)
        return user

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self._repo.get_by_telegram_id(telegram_id)

    async def update_display_name(
        self, user_id: int, display_name: str
    ) -> User | None:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        return await self._repo.update_display_name(user.id, display_name)

    async def update_avatar_key(
        self, user_id: int, avatar_key: str
    ) -> User | None:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        return await self._repo.update_avatar_key(user.id, avatar_key)
