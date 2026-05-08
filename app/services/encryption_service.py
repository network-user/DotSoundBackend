from __future__ import annotations

import base64
import os
from functools import lru_cache

import structlog
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.encryption_key import EncryptionKey

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

_KEY_CACHE: dict[int, bytes] = {}


def _get_master_key() -> bytes:
    raw = settings.chat_encryption_key
    if not raw:
        if settings.debug:
            return b"\x00" * 32
        raise RuntimeError(
            "CHAT_ENCRYPTION_KEY must be set in production"
        )
    return base64.b64decode(raw)


@lru_cache(maxsize=1)
def _master_aesgcm() -> AESGCM:
    return AESGCM(_get_master_key())


async def _get_or_create_conversation_key(
    session: AsyncSession,
    conversation_id: int,
) -> bytes:
    cached = _KEY_CACHE.get(conversation_id)
    if cached:
        return cached

    row = await session.scalar(
        select(EncryptionKey).where(
            EncryptionKey.conversation_id
            == conversation_id
        )
    )

    if row:
        master = _master_aesgcm()
        nonce = row.encrypted_key[:12]
        ciphertext = row.encrypted_key[12:]
        key = master.decrypt(nonce, ciphertext, None)
        _KEY_CACHE[conversation_id] = key
        return key

    conv_key = AESGCM.generate_key(256)
    master = _master_aesgcm()
    nonce = os.urandom(12)
    encrypted = nonce + master.encrypt(
        nonce, conv_key, None
    )

    entry = EncryptionKey(
        conversation_id=conversation_id,
        encrypted_key=encrypted,
    )
    session.add(entry)
    await session.flush()

    _KEY_CACHE[conversation_id] = conv_key
    logger.info(
        "encryption_key_created",
        conversation_id=conversation_id,
    )
    return conv_key


async def encrypt_message(
    session: AsyncSession,
    conversation_id: int,
    plaintext: str,
) -> tuple[bytes, bytes]:
    key = await _get_or_create_conversation_key(
        session, conversation_id
    )
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(
        nonce, plaintext.encode("utf-8"), None
    )
    return ciphertext, nonce


async def decrypt_message(
    session: AsyncSession,
    conversation_id: int,
    ciphertext: bytes,
    nonce: bytes,
) -> str:
    key = await _get_or_create_conversation_key(
        session, conversation_id
    )
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(
        nonce, ciphertext, None
    )
    return plaintext.decode("utf-8")


def clear_key_cache() -> None:
    _KEY_CACHE.clear()
