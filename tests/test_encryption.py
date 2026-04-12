import os
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.models.base import Base
from app.services.encryption_service import (
    clear_key_cache,
    decrypt_message,
    encrypt_message,
)

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory: async_sessionmaker[AsyncSession] = (
        async_sessionmaker(
            engine, expire_on_commit=False
        )
    )
    async with factory() as s:
        yield s  # type: ignore[misc]
    await engine.dispose()


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_key_cache()


@pytest.mark.anyio
async def test_encrypt_decrypt_roundtrip(
    session: AsyncSession,
) -> None:
    plaintext = "Hello, encrypted world!"
    ct, nonce = await encrypt_message(
        session, 1, plaintext
    )
    assert ct != plaintext.encode()
    assert len(nonce) == 12

    result = await decrypt_message(
        session, 1, ct, nonce
    )
    assert result == plaintext


@pytest.mark.anyio
async def test_different_conversations_different_keys(
    session: AsyncSession,
) -> None:
    ct1, n1 = await encrypt_message(
        session, 1, "msg A"
    )
    ct2, n2 = await encrypt_message(
        session, 2, "msg B"
    )
    assert ct1 != ct2


@pytest.mark.anyio
async def test_plaintext_not_in_ciphertext(
    session: AsyncSession,
) -> None:
    secret = "super_secret_data_12345"
    ct, _ = await encrypt_message(
        session, 1, secret
    )
    assert secret.encode() not in ct


@pytest.mark.anyio
async def test_wrong_nonce_fails(
    session: AsyncSession,
) -> None:
    ct, nonce = await encrypt_message(
        session, 1, "test"
    )
    bad_nonce = os.urandom(12)
    with pytest.raises(Exception):
        await decrypt_message(
            session, 1, ct, bad_nonce
        )
