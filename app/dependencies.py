from collections.abc import AsyncGenerator

from dotsound_private_core.services.network_policy import (
    is_ip_in_cidrs,
)
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
    is_token_revoked,
)
from app.core.client_ip import (
    internal_api_trusted_proxy_cidrs,
    resolve_request_client_ip,
)
from app.core.db import AsyncSessionLocal
from app.models.user import User
from app.repositories.user import UserRepository

_bearer = HTTPBearer(auto_error=False)
_ACCESS_COOKIE = "ds_access"


def _extract_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    if credentials and credentials.credentials:
        return credentials.credentials
    cookie = request.cookies.get(_ACCESS_COOKIE)
    return cookie or None


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


def require_internal_caller(request: Request) -> None:
    """Restrict an endpoint to internal callers only.

    Resolves the real client IP behind any trusted proxy and rejects
    anything outside ``settings.internal_api_allowed_cidrs_list`` with a
    silent 404 (mirrors InternalApiAllowlistMiddleware so external
    scanners cannot tell the route exists). Used by server-to-server
    routes such as the bot's user upsert, which reaches the backend
    directly over the internal compose network.
    """
    client_ip, _peer_ip = resolve_request_client_ip(
        request,
        internal_api_trusted_proxy_cidrs(),
    )
    if not is_ip_in_cidrs(
        client_ip, settings.internal_api_allowed_cidrs_list
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )


async def get_current_user(
    request: Request,
    credentials: (
        HTTPAuthorizationCredentials | None
    ) = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    token = _extract_token(request, credentials)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except AuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = str(payload.get("jti") or "")
    if jti and await is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked",
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
                headers={
                    "X-Account-Status": "deleted",
                },
            )
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"X-Account-Status": "banned"},
        )
    return user


async def get_optional_user(
    request: Request,
    credentials: (
        HTTPAuthorizationCredentials | None
    ) = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> User | None:
    token = _extract_token(request, credentials)
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except AuthError:
        return None
    jti = str(payload.get("jti") or "")
    if jti and await is_token_revoked(jti):
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

    Caller must hold a valid admin **session** token (issued via
    the admin TOTP login flow) AND have a matching row in
    ``admin_capabilities``. There is no implicit super-admin
    bypass: every privileged action goes through
    ``admin_capabilities`` so the audit log captures the
    capability that authorized it. Anyone else gets 401/403.

    Uses ``require_admin_session`` (admin JWT signed with
    ``ADMIN_JWT_SECRET``), not the generic user JWT. Mixing the
    two would let any admin user bypass device pinning, session
    revocation and the short admin token TTL.
    """

    async def _dep(
        user: User = Depends(require_admin_session),
        session: AsyncSession = Depends(get_db),
    ) -> User:
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
