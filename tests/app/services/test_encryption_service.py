import os

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.encryption_service import (
    clear_key_cache,
    decrypt_message,
    encrypt_message,
)

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_key_cache()


async def test_encrypt_decrypt_roundtrip(
    db_session: AsyncSession,
) -> None:
    plaintext = "Hello, encrypted world!"
    ct, nonce = await encrypt_message(
        db_session, 1, plaintext
    )
    assert ct != plaintext.encode()
    assert len(nonce) == 12

    result = await decrypt_message(
        db_session, 1, ct, nonce
    )
    assert result == plaintext


async def test_different_conversations_different_keys(
    db_session: AsyncSession,
) -> None:
    ct1, n1 = await encrypt_message(
        db_session, 1, "msg A"
    )
    ct2, n2 = await encrypt_message(
        db_session, 2, "msg B"
    )
    assert ct1 != ct2


async def test_plaintext_not_in_ciphertext(
    db_session: AsyncSession,
) -> None:
    secret = "super_secret_data_12345"
    ct, _ = await encrypt_message(
        db_session, 1, secret
    )
    assert secret.encode() not in ct


async def test_wrong_nonce_fails(
    db_session: AsyncSession,
) -> None:
    ct, nonce = await encrypt_message(
        db_session, 1, "test"
    )
    bad_nonce = os.urandom(12)
    with pytest.raises(Exception):
        await decrypt_message(
            db_session, 1, ct, bad_nonce
        )
