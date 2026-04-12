import structlog
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_telegram_id(
        self, telegram_id: int
    ) -> User | None:
        logger.debug("db_get_by_telegram_id", telegram_id=telegram_id)
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str,
        last_name: str | None,
    ) -> tuple[User, bool]:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            if not user.avatar_seed:
                user.avatar_seed = uuid.uuid4().hex
            await self._session.flush()
            logger.debug("db_user_updated", telegram_id=telegram_id)
            return user, False
        user = await self.create(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            avatar_seed=uuid.uuid4().hex,
        )
        logger.debug("db_user_created", telegram_id=telegram_id)
        return user, True

    async def update_display_name(
        self, user_id: int, display_name: str
    ) -> User | None:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        user.display_name = display_name
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def get_first_user(self) -> User | None:
        result = await self._session.execute(
            select(User).order_by(User.id).limit(1)
        )
        return result.scalar_one_or_none()

    async def update_avatar_key(
        self, user_id: int, avatar_key: str
    ) -> User | None:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        user.avatar_key = avatar_key
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def search(
        self, query: str, limit: int = 20
    ) -> list[User]:
        pattern = f"%{query}%"
        result = await self._session.execute(
            select(User)
            .where(
                User.is_active.is_(True),
                (
                    User.username.ilike(pattern)
                    | User.first_name.ilike(pattern)
                    | User.last_name.ilike(pattern)
                    | User.display_name.ilike(
                        pattern
                    )
                ),
            )
            .limit(limit)
        )
        return list(result.scalars().all())
