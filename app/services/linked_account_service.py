"""Manage OAuth-linked provider accounts for users.

Tokens are stored encrypted using Fernet symmetric encryption.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user_linked_account import UserLinkedAccount

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_SUPPORTED_PROVIDERS = frozenset({"spotify", "soundcloud", "vk"})


def _get_fernet() -> Fernet:
    key = settings.oauth_token_encryption_key or settings.totp_encryption_key
    if not key:
        raise RuntimeError(
            "Neither OAUTH_TOKEN_ENCRYPTION_KEY nor TOTP_ENCRYPTION_KEY "
            "is configured — cannot encrypt/decrypt OAuth tokens."
        )
    raw = base64.urlsafe_b64decode(key + "==")
    return Fernet(base64.urlsafe_b64encode(raw[:32]))


def _encrypt(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def _decrypt(encrypted: str) -> str:
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Failed to decrypt OAuth token") from exc


class LinkedAccountService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_account(
        self, user_id: int, provider: str
    ) -> UserLinkedAccount | None:
        result = await self._session.execute(
            select(UserLinkedAccount).where(
                UserLinkedAccount.user_id == user_id,
                UserLinkedAccount.provider == provider,
            )
        )
        return result.scalar_one_or_none()

    async def list_accounts(
        self, user_id: int
    ) -> list[UserLinkedAccount]:
        result = await self._session.execute(
            select(UserLinkedAccount).where(
                UserLinkedAccount.user_id == user_id
            )
        )
        return list(result.scalars().all())

    async def upsert_account(
        self,
        user_id: int,
        provider: str,
        access_token: str,
        refresh_token: str | None,
        expires_in: int | None,
        scopes: str | None,
        provider_user_id: str | None,
        provider_username: str | None,
    ) -> UserLinkedAccount:
        expires_at: datetime | None = None
        if expires_in is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=expires_in
            )

        values = {
            "user_id": user_id,
            "provider": provider,
            "access_token_encrypted": _encrypt(access_token),
            "refresh_token_encrypted": (
                _encrypt(refresh_token) if refresh_token else None
            ),
            "expires_at": expires_at,
            "scopes": scopes,
            "provider_user_id": provider_user_id,
            "provider_username": provider_username,
        }

        stmt = (
            pg_insert(UserLinkedAccount)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_linked_account_user_provider",
                set_={
                    k: v
                    for k, v in values.items()
                    if k not in ("user_id", "provider")
                },
            )
            .returning(UserLinkedAccount)
        )
        result = await self._session.execute(stmt)
        account = result.scalar_one()
        await self._session.commit()
        logger.info(
            "linked_account_upserted",
            user_id=user_id,
            provider=provider,
        )
        return account

    async def delete_account(
        self, user_id: int, provider: str
    ) -> None:
        account = await self.get_account(user_id, provider)
        if account:
            await self._session.delete(account)
            await self._session.commit()
            logger.info(
                "linked_account_deleted",
                user_id=user_id,
                provider=provider,
            )

    def get_decrypted_tokens(
        self, account: UserLinkedAccount
    ) -> tuple[str, str | None]:
        """Return (access_token, refresh_token | None) in plaintext."""
        access = _decrypt(account.access_token_encrypted)
        refresh = (
            _decrypt(account.refresh_token_encrypted)
            if account.refresh_token_encrypted
            else None
        )
        return access, refresh

    def is_expired(self, account: UserLinkedAccount) -> bool:
        if account.expires_at is None:
            return False
        now = datetime.now(timezone.utc)
        # Refresh 60 seconds early to avoid clock skew
        return account.expires_at <= now + timedelta(seconds=60)

    async def refresh_if_expired(
        self, account: UserLinkedAccount
    ) -> UserLinkedAccount:
        if not self.is_expired(account):
            return account

        _, refresh_token = self.get_decrypted_tokens(account)
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    f"{account.provider.capitalize()} token expired "
                    "and no refresh token is available. "
                    "Please reconnect your account."
                ),
            )

        client_id, client_secret = _get_provider_credentials(account.provider)
        try:
            from dotsound_private_core.services import refresh_oauth_token

            new_tokens: dict[str, Any] = await asyncio.to_thread(
                refresh_oauth_token,
                account.provider,
                refresh_token,
                client_id,
                client_secret,
            )
        except Exception as exc:
            logger.warning(
                "token_refresh_failed",
                provider=account.provider,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    f"Failed to refresh {account.provider.capitalize()} "
                    "token. Please reconnect your account."
                ),
            ) from exc

        return await self.upsert_account(
            user_id=account.user_id,
            provider=account.provider,
            access_token=new_tokens["access_token"],
            refresh_token=new_tokens.get("refresh_token"),
            expires_in=new_tokens.get("expires_in"),
            scopes=account.scopes,
            provider_user_id=account.provider_user_id,
            provider_username=account.provider_username,
        )


def _get_provider_credentials(provider: str) -> tuple[str, str]:
    if provider == "spotify":
        return settings.spotify_client_id, settings.spotify_client_secret
    if provider == "soundcloud":
        return (
            settings.soundcloud_oauth_client_id,
            settings.soundcloud_oauth_client_secret,
        )
    # VK tokens don't need refresh via client credentials
    return settings.vk_app_id, settings.vk_app_secret
