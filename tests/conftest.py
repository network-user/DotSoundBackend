import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.dependencies import get_db
from app.main import create_app
from app.models.base import Base

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncClient:
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory: async_sessionmaker[AsyncSession] = (
        async_sessionmaker(engine, expire_on_commit=False)
    )

    async def _override_get_db() -> AsyncSession:
        async with session_factory() as session:
            try:
                yield session  # type: ignore[misc]
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    application = create_app()
    application.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as ac:
        yield ac  # type: ignore[misc]

    await engine.dispose()
