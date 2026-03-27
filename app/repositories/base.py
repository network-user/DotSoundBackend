from typing import Any, Generic, TypeVar

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

T = TypeVar("T", bound=Base)
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class BaseRepository(Generic[T]):
    def __init__(
        self,
        session: AsyncSession,
        model: type[T],
    ) -> None:
        self._session = session
        self._model = model

    async def get_by_id(self, record_id: int) -> T | None:
        logger.debug(
            "db_get_by_id",
            model=self._model.__name__,
            id=record_id,
        )
        return await self._session.get(self._model, record_id)

    async def create(self, **kwargs: Any) -> T:
        logger.debug("db_create", model=self._model.__name__, data=kwargs)
        instance = self._model(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def delete(self, instance: T) -> None:
        logger.debug(
            "db_delete",
            model=self._model.__name__,
        )
        await self._session.delete(instance)
        await self._session.flush()

    async def count(self) -> int:
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count()).select_from(self._model)
        )
        return result.scalar_one()
