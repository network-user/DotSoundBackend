from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AppSettings, settings
from app.core.auth import (
    AuthError,
    decode_access_token,
    decode_admin_token,
)
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
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    if not user.is_active and user.deleted_at:
        from dotsound_private_core.services.account_deletion_policy import (
            is_within_grace_period,
        )
        if not is_within_grace_period(user.deleted_at):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account deleted",
            )
    elif not user.is_active:
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


def require_capability(capability: str):
    """Return a FastAPI dependency that enforces a capability.

    Caller must be an admin (``is_admin`` True) AND have a row in
    ``admin_capabilities`` matching the requested capability. There
    is no implicit super-admin bypass: every privileged action goes
    through ``admin_capabilities`` so the audit log captures the
    capability that authorized it. Anyone else gets 403.
    """

    async def _dep(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> User:
        if not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )
        from app.repositories.admin_capability import (
            AdminCapabilityRepository,
        )

        repo = AdminCapabilityRepository(session)
        if not await repo.has_capability(
            user.id, capability
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="capability required",
            )
        return user

    return _dep


async def get_admin_session(
    request: Request,
    credentials: (
        HTTPAuthorizationCredentials | None
    ) = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> tuple[User, dict[str, object]]:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_admin_token(
            credentials.credentials
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("scope") != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin scope required",
        )
    jti = str(payload.get("jti", ""))
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token missing jti",
        )

    from app.repositories.admin_device import (
        AdminDeviceRepository,
    )
    from app.repositories.admin_session import (
        AdminSessionRepository,
    )
    from app.services.admin_auth_service import (
        is_admin_session_valid,
    )

    sessions = AdminSessionRepository(session)
    row = await sessions.get_by_jti(jti)
    if not is_admin_session_valid(row=row):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin session expired or revoked",
        )
    assert row is not None

    devices = AdminDeviceRepository(session)
    device = await devices.get_by_id(row.device_id)
    if (
        device is None
        or device.revoked_at is not None
        or device.trusted_at is None
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin device not trusted",
        )

    user_id = int(str(payload["sub"]))
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if (
        not user
        or not user.is_active
        or not user.is_admin
        or not user.admin_init
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin not active",
        )

    client_host = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await sessions.touch(
        row, ip=client_host, ua=user_agent
    )
    await devices.touch(device, ip=client_host)
    return user, payload


async def require_admin_session(
    pair: tuple[User, dict[str, object]] = Depends(
        get_admin_session
    ),
) -> User:
    user, _payload = pair
    return user


def require_step_up(action: str):
    """Require a fresh step-up TOTP marker for ``action``.

    Frontend opens the StepUpDialog, the backend verifies a TOTP
    code via ``/admin/auth/step-up`` and stores a Redis marker for
    a few minutes (TTL from PrivateCore). Critical endpoints attach
    this dependency so they only fire when the marker is present.
    """

    async def _dep(
        user: User = Depends(require_admin_session),
    ) -> User:
        from app.services.admin_auth_service import (
            consume_step_up,
        )

        ok = await consume_step_up(
            user_id=user.id, action=action
        )
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Step-up authentication required"
                ),
            )
        return user

    return _dep
