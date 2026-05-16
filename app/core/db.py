from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

async_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=settings.db_pool_pre_ping,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = (
    async_sessionmaker(
        async_engine,
        expire_on_commit=False,
    )
)


async def dispose_engine() -> None:
    await async_engine.dispose()
