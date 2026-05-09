"""Admin authentication routes (TOTP onboarding, login, devices)."""

import secrets
from typing import Any

import structlog
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rate_limit import limiter
from app.dependencies import (
    get_admin_session,
    get_current_user,
    get_db,
    require_admin_session,
)
from app.middlewares.admin_security import (
    CSRF_COOKIE_NAME,
)
from app.models.user import User
from app.schemas.admin.auth import (
    AdminAuthMetadata,
    AdminBackupCodesResponse,
    AdminCsrfResponse,
    AdminDeviceApprovalRequest,
    AdminDeviceConfirmRequest,
    AdminDeviceItem,
    AdminDevicesListResponse,
    AdminDisableRequest,
    AdminInitConfirmRequest,
    AdminInitConfirmResponse,
    AdminInitStartResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMessageResponse,
    AdminRefreshRequest,
    AdminRefreshResponse,
    AdminSessionPayload,
    AdminStepUpRequest,
)
from app.services.admin_auth_service import (
    AdminAuthError,
    confirm_admin_init,
    consume_backup_code,
    disable_admin_2fa,
    is_locked_out,
    metadata_summary,
    regenerate_backup_codes,
    revoke_admin_session,
    rotate_admin_refresh,
    start_admin_init,
    verify_admin_login,
    verify_step_up,
)
from app.services.admin_device_service import (
    confirm_device_approval,
    list_devices,
    request_device_approval,
    revoke_device,
)

router = APIRouter(prefix="/auth", tags=["admin-auth"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="admin_refresh",
        value=refresh_token,
        max_age=24 * 60 * 60,
        httponly=True,
        secure=not settings.debug,
        samesite="strict",
        path=settings.admin_api_auth_prefix,
    )


def _clear_refresh_cookie(
    response: Response,
) -> None:
    response.delete_cookie(
        key="admin_refresh",
        path=settings.admin_api_auth_prefix,
    )


@router.get("/csrf", response_model=AdminCsrfResponse)
async def get_csrf(
    request: Request,
    response: Response,
) -> AdminCsrfResponse:
    existing = request.cookies.get(CSRF_COOKIE_NAME)
    if existing:
        return AdminCsrfResponse(csrf=existing)
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        max_age=12 * 60 * 60,
        httponly=False,
        secure=not settings.debug,
        samesite="strict",
        path=settings.admin_api_prefix,
    )
    return AdminCsrfResponse(csrf=token)


@router.get("/metadata", response_model=AdminAuthMetadata)
async def get_metadata(
    user: User = Depends(get_current_user),
) -> AdminAuthMetadata:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not found",
        )
    summary = metadata_summary(user=user)
    return AdminAuthMetadata(**summary)


@router.post(
    "/init/start",
    response_model=AdminInitStartResponse,
)
@limiter.limit("3/minute")
async def init_start(
    request: Request,
    user: User = Depends(get_current_user),
) -> AdminInitStartResponse:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not found",
        )
    try:
        data = await start_admin_init(user)
    except AdminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return AdminInitStartResponse(
        secret_b32=str(data["secret_b32"]),
        otpauth_uri=str(data["otpauth_uri"]),
        ttl_seconds=int(data["ttl_seconds"]),  # type: ignore[arg-type]
    )


@router.post(
    "/init/confirm",
    response_model=AdminInitConfirmResponse,
)
@limiter.limit("5/minute")
async def init_confirm(
    request: Request,
    response: Response,
    payload: AdminInitConfirmRequest = Body(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AdminInitConfirmResponse:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not found",
        )
    try:
        result = await confirm_admin_init(
            user=user,
            code=payload.code,
            fingerprint=payload.fingerprint,
            label=payload.label,
            ip=_client_ip(request),
            ua=_user_agent(request),
            session=session,
        )
    except AdminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    issued = result["session"]
    assert isinstance(issued, dict)
    _set_refresh_cookie(response, str(issued["refresh_token"]))
    return AdminInitConfirmResponse(
        backup_codes=list(result["backup_codes"]),  # type: ignore[arg-type]
        device_id=int(result["device_id"]),  # type: ignore[arg-type]
        session=AdminSessionPayload(
            access_token=str(issued["access_token"]),
            refresh_token=str(issued["refresh_token"]),
            expires_in=int(issued["expires_in"]),  # type: ignore[arg-type]
            jti=str(issued["jti"]),
            refresh_jti=str(issued["refresh_jti"]),
            session_id=int(issued["session_id"]),  # type: ignore[arg-type]
        ),
    )


@router.post("/login", response_model=AdminLoginResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    payload: AdminLoginRequest = Body(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AdminLoginResponse:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not found",
        )
    if await is_locked_out(user.id):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="account locked out",
        )
    try:
        result = await verify_admin_login(
            user=user,
            code=payload.code,
            fingerprint=payload.fingerprint,
            ip=_client_ip(request),
            ua=_user_agent(request),
            session=session,
        )
    except AdminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    if result.get("requires_device_approval"):
        return AdminLoginResponse(
            requires_device_approval=True,
            device_id=int(result["device_id"]),  # type: ignore[arg-type]
        )
    issued = result["session"]
    assert isinstance(issued, dict)
    _set_refresh_cookie(response, str(issued["refresh_token"]))
    return AdminLoginResponse(
        requires_device_approval=False,
        session=AdminSessionPayload(
            access_token=str(issued["access_token"]),
            refresh_token=str(issued["refresh_token"]),
            expires_in=int(issued["expires_in"]),  # type: ignore[arg-type]
            jti=str(issued["jti"]),
            refresh_jti=str(issued["refresh_jti"]),
            session_id=int(issued["session_id"]),  # type: ignore[arg-type]
        ),
    )


@router.post(
    "/devices/request-approval",
    response_model=AdminMessageResponse,
)
@limiter.limit("20/minute")
async def devices_request_approval(
    request: Request,
    payload: AdminDeviceApprovalRequest = Body(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AdminMessageResponse:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not found",
        )
    try:
        await request_device_approval(
            user=user,
            device_id=payload.device_id,
            force_resend=payload.force_resend,
            session=session,
        )
    except AdminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return AdminMessageResponse(detail="approval code sent")


@router.post(
    "/devices/confirm",
    response_model=AdminLoginResponse,
)
@limiter.limit("5/minute")
async def devices_confirm(
    request: Request,
    response: Response,
    payload: AdminDeviceConfirmRequest = Body(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AdminLoginResponse:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not found",
        )
    try:
        result = await confirm_device_approval(
            user=user,
            device_id=payload.device_id,
            email_code=payload.email_code,
            totp_code=payload.totp_code,
            label=payload.label,
            ip=_client_ip(request),
            ua=_user_agent(request),
            session=session,
        )
    except AdminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    issued = result["session"]
    assert isinstance(issued, dict)
    _set_refresh_cookie(response, str(issued["refresh_token"]))
    return AdminLoginResponse(
        requires_device_approval=False,
        device_id=int(result["device_id"]),  # type: ignore[arg-type]
        session=AdminSessionPayload(
            access_token=str(issued["access_token"]),
            refresh_token=str(issued["refresh_token"]),
            expires_in=int(issued["expires_in"]),  # type: ignore[arg-type]
            jti=str(issued["jti"]),
            refresh_jti=str(issued["refresh_jti"]),
            session_id=int(issued["session_id"]),  # type: ignore[arg-type]
        ),
    )


@router.post("/step-up", response_model=AdminMessageResponse)
@limiter.limit("10/minute")
async def step_up(
    request: Request,
    payload: AdminStepUpRequest = Body(...),
    user: User = Depends(require_admin_session),
) -> AdminMessageResponse:
    try:
        ok = await verify_step_up(
            user=user,
            code=payload.code,
            action=payload.action,
        )
    except AdminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid step-up code",
        )
    return AdminMessageResponse(detail="step-up confirmed")


@router.post("/refresh", response_model=AdminRefreshResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    payload: AdminRefreshRequest | None = None,
    session: AsyncSession = Depends(get_db),
) -> AdminRefreshResponse:
    cookie_token = request.cookies.get("admin_refresh")
    body_token = payload.refresh_token if payload else None
    refresh_token = body_token or cookie_token
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh token required",
        )
    try:
        result = await rotate_admin_refresh(
            refresh_token=refresh_token,
            ip=_client_ip(request),
            ua=_user_agent(request),
            session=session,
        )
    except AdminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    _set_refresh_cookie(response, str(result["refresh_token"]))
    return AdminRefreshResponse(
        access_token=str(result["access_token"]),
        refresh_token=str(result["refresh_token"]),
        expires_in=int(result["expires_in"]),  # type: ignore[arg-type]
    )


@router.post("/logout", response_model=AdminMessageResponse)
async def logout(
    response: Response,
    pair: tuple[User, dict[str, object]] = Depends(get_admin_session),
    session: AsyncSession = Depends(get_db),
) -> AdminMessageResponse:
    _user, payload = pair
    jti = str(payload.get("jti", ""))
    if jti:
        await revoke_admin_session(jti=jti, session=session)
    _clear_refresh_cookie(response)
    return AdminMessageResponse(detail="logged out")


@router.get(
    "/devices",
    response_model=AdminDevicesListResponse,
)
async def devices_list(
    user: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> AdminDevicesListResponse:
    rows = await list_devices(user=user, session=session)
    return AdminDevicesListResponse(
        items=[AdminDeviceItem(**row) for row in rows]  # type: ignore[arg-type]
    )


@router.delete(
    "/devices/{device_id}",
    response_model=AdminMessageResponse,
)
async def devices_revoke(
    device_id: int,
    user: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> AdminMessageResponse:
    try:
        await revoke_device(
            user=user,
            device_id=device_id,
            session=session,
        )
    except AdminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return AdminMessageResponse(detail="revoked")


def _require_step_up(action: str) -> Any:  # noqa: ANN401
    from app.dependencies import require_step_up

    return require_step_up(action)


@router.post(
    "/regenerate-backup-codes",
    response_model=AdminBackupCodesResponse,
)
async def regenerate_codes(
    user: User = Depends(_require_step_up("auth.regenerate_backup_codes")),
    session: AsyncSession = Depends(get_db),
) -> AdminBackupCodesResponse:
    try:
        codes = await regenerate_backup_codes(user=user, session=session)
    except AdminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return AdminBackupCodesResponse(backup_codes=codes)


@router.post("/disable", response_model=AdminMessageResponse)
async def disable(
    payload: AdminDisableRequest = Body(...),
    user: User = Depends(_require_step_up("auth.disable")),
    session: AsyncSession = Depends(get_db),
) -> AdminMessageResponse:
    try:
        await disable_admin_2fa(
            user=user,
            code=payload.code,
            session=session,
        )
    except AdminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return AdminMessageResponse(detail="admin 2FA disabled")


@router.post(
    "/backup-code/use",
    response_model=AdminMessageResponse,
)
async def use_backup_code(
    payload: AdminDisableRequest = Body(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AdminMessageResponse:
    if not user.is_admin or not user.admin_init:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not found",
        )
    if not await consume_backup_code(
        user=user, code=payload.code, session=session
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid backup code",
        )
    return AdminMessageResponse(detail="backup code consumed")


__all__ = ["router"]
