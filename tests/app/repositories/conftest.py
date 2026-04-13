from typing import Any

import pytest
from sqlalchemy import BigInteger, Boolean, event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles

import app.models  # noqa: F401
from app.models.base import Base
from tests.factories import TrackFactory, UserFactory

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@compiles(BigInteger, "sqlite")
def _compile_bigint_sqlite(
    _type: BigInteger,
    _compiler: Any,
    **_kwargs: Any,
) -> str:
    return "INTEGER"


@event.listens_for(Base, "init", propagate=True)
def _set_boolean_defaults(
    target: Any,
    _args: Any,
    kwargs: dict[str, Any],
) -> None:
    for attr in type(target).__mapper__.column_attrs:
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


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session():
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory: async_sessionmaker[AsyncSession] = (
        async_sessionmaker(
            engine, expire_on_commit=False
        )
    )
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def create_user(session: AsyncSession):
    async def _create(**kwargs: Any):
        user = UserFactory(**kwargs)
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user

    return _create


@pytest.fixture
def create_track(
    session: AsyncSession,
    create_user,
):
    async def _create(**kwargs: Any):
        if "uploaded_by_id" not in kwargs:
            user = await create_user()
            kwargs["uploaded_by_id"] = user.id
        track = TrackFactory(**kwargs)
        session.add(track)
        await session.flush()
        await session.refresh(track)
        return track

    return _create
