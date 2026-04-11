from io import BytesIO
from typing import Any
from unittest.mock import AsyncMock, patch

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
        async_sessionmaker(
            engine, expire_on_commit=False
        )
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
    application.dependency_overrides[get_db] = (
        _override_get_db
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as ac:
        yield ac  # type: ignore[misc]

    await engine.dispose()


@pytest.fixture
def mock_s3():
    with patch(
        "app.core.s3.upload_audio",
        new_callable=AsyncMock,
        return_value="anon/testkey.mp3",
    ) as m:
        yield m


async def create_test_user(
    client: AsyncClient,
    telegram_id: int,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = {
        "telegram_id": telegram_id,
        "first_name": kwargs.get("first_name", "Test"),
        "username": kwargs.get("username"),
        "last_name": kwargs.get("last_name"),
    }
    r = await client.post("/api/v1/users", json=payload)
    assert r.status_code == 200
    return r.json()


async def create_test_track(
    client: AsyncClient,
    title: str = "Test Track",
    uploader_id: int | None = None,
) -> dict[str, Any]:
    data: dict[str, str] = {"title": title}
    if uploader_id is not None:
        data["uploader_id"] = str(uploader_id)

    with patch(
        "app.core.s3.upload_audio",
        new_callable=AsyncMock,
        return_value=f"anon/{title}.mp3",
    ):
        r = await client.post(
            "/api/v1/tracks/upload",
            data=data,
            files={
                "file": (
                    "t.mp3",
                    BytesIO(b"\xff\xfb" + b"\x00" * 64),
                    "audio/mpeg",
                )
            },
        )
    assert r.status_code == 201
    return r.json()
