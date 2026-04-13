from io import BytesIO
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import BigInteger, Boolean, event
from sqlalchemy.ext.compiler import compiles
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


@compiles(BigInteger, "sqlite")
def _compile_bigint_sqlite(
    _type: BigInteger,
    _compiler: Any,
    **_kwargs: Any,
) -> str:
    return "INTEGER"


@event.listens_for(
    Base, "init", propagate=True
)
def _set_boolean_defaults(
    target: Any,
    _args: Any,
    kwargs: dict[str, Any],
) -> None:
    for attr in type(
        target
    ).__mapper__.column_attrs:
        col = attr.columns[0]
        if (
            isinstance(col.type, Boolean)
            and attr.key not in kwargs
            and col.server_default is not None
        ):
            sd = col.server_default.arg
            if isinstance(sd, str):
                setattr(
                    target,
                    attr.key,
                    sd.lower() in ("true", "1"),
                )


@pytest.fixture(autouse=True)
def _disable_rate_limit():
    with patch(
        "app.core.rate_limit.limiter.enabled",
        False,
    ):
        yield


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_engine():
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    factory: async_sessionmaker[AsyncSession] = (
        async_sessionmaker(
            db_engine, expire_on_commit=False
        )
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def client(db_engine) -> AsyncClient:
    factory: async_sessionmaker[AsyncSession] = (
        async_sessionmaker(
            db_engine, expire_on_commit=False
        )
    )

    async def _override_get_db() -> AsyncSession:
        async with factory() as session:
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


@pytest.fixture
def mock_s3():
    with patch(
        "app.core.s3.upload_audio",
        new_callable=AsyncMock,
        return_value="anon/testkey.mp3",
    ) as m:
        yield m


@pytest.fixture
def mock_taskiq():
    with patch(
        "app.services.upload_service"
        ".transcode_and_upload.kiq",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.upload_service"
        ".generate_and_upload_cover.kiq",
        new_callable=AsyncMock,
        return_value=None,
    ):
        yield


async def create_test_user(
    client: AsyncClient,
    telegram_id: int,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = {
        "telegram_id": telegram_id,
        "first_name": kwargs.get(
            "first_name", "Test"
        ),
        "username": kwargs.get("username"),
        "last_name": kwargs.get("last_name"),
    }
    r = await client.post(
        "/api/v1/users", json=payload
    )
    assert r.status_code == 200
    return r.json()


async def create_test_track(
    client: AsyncClient,
    title: str = "Test Track",
    uploader_id: int | None = None,
) -> dict[str, Any]:
    data: dict[str, str] = {"title": title}
    headers: dict[str, str] = {}
    if uploader_id is not None:
        headers = await auth_headers(
            client, uploader_id
        )

    with patch(
        "app.core.s3.upload_audio",
        new_callable=AsyncMock,
        return_value=f"anon/{title}.mp3",
    ), patch(
        "app.services.upload_service"
        ".transcode_and_upload.kiq",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.upload_service"
        ".generate_and_upload_cover.kiq",
        new_callable=AsyncMock,
        return_value=None,
    ):
        r = await client.post(
            "/api/v1/tracks/upload",
            data=data,
            headers=headers,
            files={
                "file": (
                    "t.mp3",
                    BytesIO(
                        b"\xff\xfb" + b"\x00" * 64
                    ),
                    "audio/mpeg",
                )
            },
        )
    assert r.status_code == 201
    return r.json()


async def auth_headers(
    client: AsyncClient,
    user_id: int,
) -> dict[str, str]:
    response = await client.post(
        f"/api/v1/auth/mock/{user_id}"
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
