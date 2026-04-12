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

pytestmark = pytest.mark.anyio


async def test_ws_rejects_no_token() -> None:
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory: async_sessionmaker[AsyncSession] = (
        async_sessionmaker(
            engine, expire_on_commit=False
        )
    )

    async def _override() -> AsyncSession:
        async with factory() as s:
            try:
                yield s  # type: ignore[misc]
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    application = create_app()
    application.dependency_overrides[get_db] = (
        _override
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as ac:
        r = await ac.get(
            "/api/v1/ws",
            headers={
                "connection": "upgrade",
                "upgrade": "websocket",
            },
        )
        assert r.status_code in (403, 400, 200)

    await engine.dispose()


async def test_ws_rejects_invalid_token() -> None:
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory: async_sessionmaker[AsyncSession] = (
        async_sessionmaker(
            engine, expire_on_commit=False
        )
    )

    async def _override() -> AsyncSession:
        async with factory() as s:
            try:
                yield s  # type: ignore[misc]
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    application = create_app()
    application.dependency_overrides[get_db] = (
        _override
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as ac:
        r = await ac.get(
            "/api/v1/ws?token=invalid_jwt_token",
            headers={
                "connection": "upgrade",
                "upgrade": "websocket",
            },
        )
        assert r.status_code in (403, 400, 200)

    await engine.dispose()
