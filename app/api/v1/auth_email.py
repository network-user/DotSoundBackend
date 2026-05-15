import hashlib

import structlog
from dotsound_private_core.services import (
    mask_ip,
    parse_user_agent,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth_cookie import set_access_cookie
from app.core.rate_limit import limiter
from app.core.redis import get_redis_client
from app.dependencies import get_current_user, get_db
from app.models.login_history import LoginHistory
from app.models.user import User
from app.schemas.auth_email import (
    EmailAuthRequest,
    EmailAuthResponse,
    EmailVerifyRequest,
    EmailVerifyResponse,
    TwoFAConfirmRequest,
    TwoFAEmailFallbackRequest,
    TwoFASetupResponse,
    TwoFAVerifyRequest,
)
from app.services.email_auth_service import (
    EmailAuthError,
    confirm_2fa,
    disable_2fa,
    request_magic_link,
    send_2fa_fallback,
    setup_2fa,
    verify_2fa,
    verify_2fa_email_code,
    verify_magic_link,
)

router = APIRouter(
    prefix="/auth/email", tags=["auth-email"]
)
router_2fa = APIRouter(
    prefix="/auth/2fa", tags=["auth-2fa"]
)

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


def _record_login(
    request: Request,
    session: AsyncSession,
    user_id: int,
) -> None:
    client_ip = (
        request.client.host
        if request.client
        else "unknown"
    )
    user_agent = request.headers.get(
        "user-agent", ""
    )
    session.add(
        LoginHistory(
            user_id=user_id,
            ip=mask_ip(client_ip),
            device=parse_user_agent(user_agent),
            login_type="email_magic_link",
        )
    )


_MAGIC_LINK_PER_EMAIL_LIMIT = 5
_MAGIC_LINK_PER_EMAIL_WINDOW_SECONDS = 3600


async def _enforce_per_email_magic_link_limit(email: str) -> None:
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
    key = f"auth:email:magic:{digest}"
    redis = get_redis_client()
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, _MAGIC_LINK_PER_EMAIL_WINDOW_SECONDS)
    if count > _MAGIC_LINK_PER_EMAIL_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many magic-link requests for this email.",
        )


@router.post(
    "/request",
    response_model=EmailAuthResponse,
)
@limiter.limit("10/minute")
async def email_auth_request(
    request: Request,
    body: EmailAuthRequest,
) -> EmailAuthResponse:
    if not settings.resend_api_key:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail="Email auth is not configured",
        )

    await _enforce_per_email_magic_link_limit(body.email)

    client_ip = (
        request.client.host
        if request.client
        else "unknown"
    )

    from app.core.tor_checker import (
        is_tor_exit_node,
    )

    if await is_tor_exit_node(client_ip):
        logger.warning(
            "tor_exit_node_email_request",
            ip=client_ip,
            email=body.email,
        )

    try:
        await request_magic_link(body.email)
    except Exception:
        logger.exception(
            "magic_link_request_failed",
            email=body.email,
        )

    return EmailAuthResponse()


@router.post(
    "/verify",
    response_model=EmailVerifyResponse,
)
@limiter.limit("10/minute")
async def email_auth_verify(
    request: Request,
    response: Response,
    body: EmailVerifyRequest,
    session: AsyncSession = Depends(get_db),
) -> EmailVerifyResponse:
    try:
        result = await verify_magic_link(
            body.token, session
        )
    except EmailAuthError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=str(exc),
        )

    if result.get("requires_2fa"):
        return EmailVerifyResponse(
            requires_2fa=True,
            session_token=str(
                result["session_token"]
            ),
        )

    _record_login(
        request, session, int(str(result["user_id"]))
    )

    from app.services.abuse_guard import evaluate_auth_event

    await evaluate_auth_event(
        request,
        session=session,
        kind="login",
        user_id=int(str(result["user_id"])),
    )
    set_access_cookie(response, str(result["access_token"]))

    return EmailVerifyResponse(
        access_token=str(result["access_token"]),
        user_id=int(str(result["user_id"])),
        is_admin=bool(result.get("is_admin")),
    )


@router_2fa.post(
    "/verify",
    response_model=EmailVerifyResponse,
)
@limiter.limit("10/minute")
async def twofa_verify(
    request: Request,
    response: Response,
    body: TwoFAVerifyRequest,
    session: AsyncSession = Depends(get_db),
) -> EmailVerifyResponse:
    try:
        result = await verify_2fa(
            body.session_token,
            body.code,
            body.backup_code,
            session,
        )
    except EmailAuthError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=str(exc),
        )

    _record_login(
        request, session, int(str(result["user_id"]))
    )
    set_access_cookie(response, str(result["access_token"]))

    return EmailVerifyResponse(
        access_token=str(result["access_token"]),
        user_id=int(str(result["user_id"])),
        is_admin=bool(result.get("is_admin")),
    )


@router_2fa.post(
    "/setup",
    response_model=TwoFASetupResponse,
)
async def twofa_setup(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TwoFASetupResponse:
    try:
        result = await setup_2fa(user)
    except EmailAuthError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        )

    return TwoFASetupResponse(
        otpauth_uri=str(result["otpauth_uri"]),
        qr_code_base64=str(
            result["qr_code_base64"]
        ),
        backup_codes=list(result["backup_codes"]),  # type: ignore[arg-type]
    )


@router_2fa.post("/confirm")
async def twofa_confirm(
    body: TwoFAConfirmRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    try:
        await confirm_2fa(user, body.code)
    except EmailAuthError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        )
    return {"status": "2fa_enabled"}


@router_2fa.delete("")
async def twofa_disable(
    body: TwoFAConfirmRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    try:
        await disable_2fa(user, body.code)
    except EmailAuthError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        )
    return {"status": "2fa_disabled"}


@router_2fa.post("/email-fallback")
@limiter.limit("3/minute")
async def twofa_email_fallback(
    request: Request,
    body: TwoFAEmailFallbackRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    try:
        await send_2fa_fallback(
            body.session_token, session
        )
    except EmailAuthError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        )
    return {"status": "code_sent"}


@router_2fa.post(
    "/email-fallback/verify",
    response_model=EmailVerifyResponse,
)
@limiter.limit("10/minute")
async def twofa_email_fallback_verify(
    request: Request,
    response: Response,
    body: TwoFAVerifyRequest,
    session: AsyncSession = Depends(get_db),
) -> EmailVerifyResponse:
    if not body.code:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail="Code is required",
        )
    try:
        result = await verify_2fa_email_code(
            body.session_token,
            body.code,
            session,
        )
    except EmailAuthError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=str(exc),
        )
    set_access_cookie(response, str(result["access_token"]))

    return EmailVerifyResponse(
        access_token=str(result["access_token"]),
        user_id=int(str(result["user_id"])),
        is_admin=bool(result.get("is_admin")),
    )
