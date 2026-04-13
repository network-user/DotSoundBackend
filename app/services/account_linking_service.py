from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

import structlog
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import _ALGORITHM
from app.core.disposable_email import (
    is_disposable_email,
)
from app.models.account_merge import AccountMerge
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.email_sender import (
    send_magic_link,
)

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)

_LINK_EMAIL_TYPE = "link_email"
_LINK_PREFIX = "link_email:"
_LINK_TG_PREFIX = "link_tg:"
_LINK_TTL = 900


class LinkingError(Exception):
    pass


class LinkConflict(Exception):
    def __init__(
        self,
        message: str,
        has_telegram: bool = False,
        has_email: bool = False,
        can_merge: bool = False,
    ) -> None:
        super().__init__(message)
        self.has_telegram = has_telegram
        self.has_email = has_email
        self.can_merge = can_merge


async def _get_redis():  # type: ignore[no-untyped-def]
    import redis.asyncio as aioredis

    return aioredis.from_url(settings.redis_url)


def _create_link_email_token(
    user_id: int, email: str
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        seconds=_LINK_TTL,
    )
    payload: dict[str, object] = {
        "sub": str(user_id),
        "email": email.lower().strip(),
        "type": _LINK_EMAIL_TYPE,
        "exp": expire,
        "jti": secrets.token_hex(16),
    }
    return str(
        jwt.encode(
            payload,
            settings.jwt_secret,
            algorithm=_ALGORITHM,
        )
    )


async def request_link_email(
    user: User, email: str
) -> None:
    normalized = email.lower().strip()

    if is_disposable_email(normalized):
        raise LinkingError("Disposable email")

    if user.email == normalized:
        return

    token = _create_link_email_token(
        user.id, normalized
    )
    token_hash = hashlib.sha256(
        token.encode()
    ).hexdigest()

    redis = await _get_redis()
    await redis.setex(
        f"{_LINK_PREFIX}{token_hash}",
        _LINK_TTL,
        json.dumps(
            {
                "user_id": user.id,
                "email": normalized,
            }
        ),
    )
    await redis.aclose()

    base_url = settings.mini_app_url
    if not base_url.endswith("/"):
        base_url += "/"
    link = f"{base_url}?link_email_token={token}"
    await send_magic_link(normalized, link)


async def verify_link_email(
    token: str, session: AsyncSession
) -> User:
    try:
        payload = dict(
            jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[_ALGORITHM],
            )
        )
    except JWTError as exc:
        raise LinkingError(
            "Invalid or expired token"
        ) from exc

    if payload.get("type") != _LINK_EMAIL_TYPE:
        raise LinkingError("Invalid token type")

    user_id = int(str(payload["sub"]))
    email = str(payload["email"])

    token_hash = hashlib.sha256(
        token.encode()
    ).hexdigest()
    redis = await _get_redis()
    stored = await redis.get(
        f"{_LINK_PREFIX}{token_hash}"
    )
    if not stored:
        await redis.aclose()
        raise LinkingError(
            "Token already used or expired"
        )
    await redis.delete(
        f"{_LINK_PREFIX}{token_hash}"
    )
    await redis.aclose()

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise LinkingError("User not found")

    existing = await repo.get_by_email(email)
    if existing and existing.id != user.id:
        can_merge = (
            existing.telegram_id is None
            or user.telegram_id is None
        )
        raise LinkConflict(
            "Email already linked to another account",
            has_telegram=(
                existing.telegram_id is not None
            ),
            has_email=True,
            can_merge=can_merge,
        )

    user.email = email
    user.email_verified = True
    await session.flush()
    await session.refresh(user)

    logger.info(
        "email_linked",
        user_id=user.id,
        email=email,
    )
    return user


async def generate_link_telegram_code(
    user: User,
) -> str:
    code = secrets.token_hex(16)
    redis = await _get_redis()
    await redis.setex(
        f"{_LINK_TG_PREFIX}{code}",
        _LINK_TTL,
        str(user.id),
    )
    await redis.aclose()
    return code


async def verify_link_telegram(
    code: str,
    telegram_id: int,
    session: AsyncSession,
) -> User:
    redis = await _get_redis()
    key = f"{_LINK_TG_PREFIX}{code}"
    stored = await redis.get(key)
    if not stored:
        await redis.aclose()
        raise LinkingError(
            "Code expired or not found"
        )
    await redis.delete(key)
    await redis.aclose()

    user_id = int(stored.decode())
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise LinkingError("User not found")

    existing = await repo.get_by_telegram_id(
        telegram_id
    )
    if existing and existing.id != user.id:
        can_merge = (
            existing.email is None
            or user.email is None
        )
        raise LinkConflict(
            "Telegram already linked "
            "to another account",
            has_telegram=True,
            has_email=existing.email is not None,
            can_merge=can_merge,
        )

    user.telegram_id = telegram_id
    await session.flush()
    await session.refresh(user)

    logger.info(
        "telegram_linked",
        user_id=user.id,
        telegram_id=telegram_id,
    )
    return user


_TABLES_TO_MIGRATE = [
    ("tracks", "uploaded_by_id"),
    ("likes", "user_id"),
    ("dislikes", "user_id"),
    ("playlists", "owner_id"),
    ("user_follows", "follower_id"),
    ("user_follows", "following_id"),
    ("complaints", "reporter_id"),
    ("login_history", "user_id"),
    ("track_comments", "user_id"),
]


async def merge_accounts(
    source_token: str,
    target_user: User,
    session: AsyncSession,
) -> User:
    from app.core.auth import decode_access_token

    try:
        payload = decode_access_token(
            source_token
        )
    except Exception as exc:
        raise LinkingError(
            "Invalid source account token"
        ) from exc

    source_id = int(str(payload["sub"]))

    repo = UserRepository(session)
    source = await repo.get_by_id(source_id)
    if not source:
        raise LinkingError(
            "Source account not found"
        )
    if source.id == target_user.id:
        raise LinkingError(
            "Cannot merge with self"
        )

    if (
        source.telegram_id
        and target_user.telegram_id
        and source.email
        and target_user.email
    ):
        raise LinkConflict(
            "Both accounts are fully linked",
            has_telegram=True,
            has_email=True,
            can_merge=False,
        )

    summary_parts: list[str] = []

    if (
        source.telegram_id
        and not target_user.telegram_id
    ):
        target_user.telegram_id = (
            source.telegram_id
        )
        summary_parts.append(
            f"telegram_id={source.telegram_id}"
        )
    if source.email and not target_user.email:
        target_user.email = source.email
        target_user.email_verified = (
            source.email_verified
        )
        summary_parts.append(
            f"email={source.email}"
        )
    if (
        source.username
        and not target_user.username
    ):
        target_user.username = source.username

    from sqlalchemy import text

    for table, column in _TABLES_TO_MIGRATE:
        await session.execute(
            text(
                f"UPDATE {table} "
                f"SET {column} = :target "
                f"WHERE {column} = :source"
            ),
            {
                "target": target_user.id,
                "source": source.id,
            },
        )
        summary_parts.append(f"migrated:{table}")

    source.is_active = False
    source.telegram_id = None
    source.email = None

    session.add(
        AccountMerge(
            source_user_id=source.id,
            target_user_id=target_user.id,
            merged_data_summary="; ".join(
                summary_parts
            ),
        )
    )

    await session.flush()
    await session.refresh(target_user)

    logger.info(
        "accounts_merged",
        source_id=source.id,
        target_id=target_user.id,
        summary="; ".join(summary_parts),
    )
    return target_user
