from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AppSettings, settings
from app.core.auth import AuthError, decode_access_token
from app.core.db import AsyncSessionLocal
from app.models.user import User
from app.repositories.user import UserRepository

_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_settings() -> AppSettings:
    return settings


async def get_current_user(
    credentials: (
        HTTPAuthorizationCredentials | None
    ) = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(
            credentials.credentials
        )
    except AuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(str(payload["sub"]))
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        user = await repo.get_by_telegram_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


async def get_optional_user(
    credentials: (
        HTTPAuthorizationCredentials | None
    ) = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    try:
        payload = decode_access_token(
            credentials.credentials
        )
    except AuthError:
        return None
    user_id = int(str(payload["sub"]))
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        user = await repo.get_by_telegram_id(user_id)
    if not user or not user.is_active:
        return None
    return user


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
