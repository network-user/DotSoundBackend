import hmac
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from dotsound_private_core.contracts import (
    INTERNAL_SECRET_HEADER,
)
from dotsound_private_core.services import (
    build_internal_headers,
    generate_code,
    mask_ip,
    parse_user_agent,
    send_login_notification_url,
)
from dotsound_private_core.services.auth_policy import (
    CODE_PREFIX,
    CODE_TTL,
    COOLDOWN_PREFIX,
    COOLDOWN_TTL,
    INTERNAL_TOKEN_SCOPE,
    INTERNAL_TOKEN_TTL_MIN,
    is_internal_ip,
    normalize_code,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import (
    AuthError,
    create_access_token,
    create_scoped_token,
    verify_telegram_init_data,
)
from app.core.rate_limit import limiter
from app.dependencies import get_db
from app.schemas.auth import (
    TelegramAuthRequest,
    TokenResponse,
)
from app.schemas.user import UserCreate
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])
logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)

_redis_client: Any = None


async def _get_redis() -> Any:
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as aioredis

        _redis_client = aioredis.from_url(
            settings.redis_url
        )
    return _redis_client


class AuthConfigResponse(BaseModel):
    bot_username: str


@router.get("/config", response_model=AuthConfigResponse)
async def get_auth_config() -> AuthConfigResponse:
    return AuthConfigResponse(
        bot_username=settings.telegram_bot_username,
    )


@router.post(
    "/telegram",
    response_model=TokenResponse,
)
@limiter.limit("20/minute")
async def auth_telegram(
    request: Request,
    body: TelegramAuthRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    if not settings.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram auth is not configured",
        )
    try:
        tg_user = verify_telegram_init_data(
            body.init_data
        )
    except AuthError as exc:
        logger.warning(
            "telegram_auth_failed", error=str(exc)
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    service = UserService(session)
    user_data = UserCreate(
        telegram_id=int(tg_user["id"]),  # type: ignore[arg-type]
        username=(
            str(tg_user["username"])
            if tg_user.get("username")
            else None
        ),
        first_name=str(
            tg_user.get("first_name", "")
        ),
        last_name=(
            str(tg_user["last_name"])
            if tg_user.get("last_name")
            else None
        ),
    )
    user, created = (
        await service.register_or_update(user_data)
    )
    token = create_access_token(
        user.id, user.is_admin
    )
    logger.info(
        "telegram_auth_success",
        user_id=user.id,
        created=created,
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        is_admin=user.is_admin,
    )


class GenerateCodeRequest(BaseModel):
    telegram_id: int


class GenerateCodeResponse(BaseModel):
    code: str
    expires_in: int = CODE_TTL


@router.post(
    "/generate-code",
    response_model=GenerateCodeResponse,
)
async def generate_auth_code(
    request: Request,
    body: GenerateCodeRequest,
) -> GenerateCodeResponse:
    if not settings.bot_internal_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal secret not configured",
        )
    secret = request.headers.get(
        INTERNAL_SECRET_HEADER, ""
    )
    if secret != settings.bot_internal_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    redis = await _get_redis()

    cooldown_key = (
        f"{COOLDOWN_PREFIX}{body.telegram_id}"
    )
    if await redis.exists(cooldown_key):
        raise HTTPException(
            status_code=(
                status.HTTP_429_TOO_MANY_REQUESTS
            ),
            detail="Too many failed attempts. "
            "Try again later",
        )

    code = generate_code()
    await redis.setex(
        f"{CODE_PREFIX}{code}",
        CODE_TTL,
        str(body.telegram_id),
    )
    logger.info(
        "auth_code_generated",
        telegram_id=body.telegram_id,
    )
    return GenerateCodeResponse(code=code)


class CodeVerifyRequest(BaseModel):
    code: str


@router.post(
    "/verify-code",
    response_model=TokenResponse,
)
@limiter.limit("5/minute")
async def verify_telegram_code(
    request: Request,
    body: CodeVerifyRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    clean_code = normalize_code(body.code)
    redis = await _get_redis()
    key = f"{CODE_PREFIX}{clean_code}"
    stored_tg_id = await redis.get(key)

    if not stored_tg_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Code expired or not found",
        )

    telegram_id = int(stored_tg_id.decode())
    await redis.delete(key)

    service = UserService(session)
    user = await service.get_by_telegram_id(
        telegram_id
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    token = create_access_token(
        user.id, user.is_admin
    )

    client_ip = (
        request.client.host
        if request.client
        else "unknown"
    )
    user_agent = request.headers.get(
        "user-agent", ""
    )
    now = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient(
            timeout=10
        ) as client:
            await client.post(
                send_login_notification_url(
                    settings.bot_internal_url
                ),
                headers=build_internal_headers(
                    settings.bot_internal_secret
                ),
                json={
                    "telegram_id": telegram_id,
                    "ip": mask_ip(client_ip),
                    "device": parse_user_agent(
                        user_agent
                    ),
                    "time": now.strftime(
                        "%d.%m.%Y, %H:%M UTC"
                    ),
                },
            )
    except Exception:
        pass

    from app.models.login_history import (
        LoginHistory,
    )

    session.add(
        LoginHistory(
            user_id=user.id,
            ip=mask_ip(client_ip),
            device=parse_user_agent(user_agent),
            login_type="web_code",
        )
    )

    logger.info(
        "web_auth_success",
        user_id=user.id,
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        is_admin=user.is_admin,
    )


class InternalTokenRequest(BaseModel):
    telegram_id: int


@router.post(
    "/internal-token",
    response_model=TokenResponse,
    include_in_schema=False,
)
@limiter.limit("5/minute")
async def internal_token(
    request: Request,
    body: InternalTokenRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    client_ip = (
        request.client.host
        if request.client
        else "unknown"
    )

    if not is_internal_ip(client_ip):
        logger.warning(
            "internal_token_blocked_ip",
            ip=client_ip,
            telegram_id=body.telegram_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    if not settings.bot_internal_secret:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail="Internal secret not configured",
        )

    provided = (
        request.headers.get(
            INTERNAL_SECRET_HEADER, ""
        )
        .encode()
    )
    expected = (
        settings.bot_internal_secret.encode()
    )
    if not hmac.compare_digest(provided, expected):
        logger.warning(
            "internal_token_bad_secret",
            ip=client_ip,
            telegram_id=body.telegram_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    service = UserService(session)
    user = await service.get_by_telegram_id(
        body.telegram_id
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    token = create_scoped_token(
        user.id,
        scope=INTERNAL_TOKEN_SCOPE,
        ttl_minutes=INTERNAL_TOKEN_TTL_MIN,
    )

    user_agent = request.headers.get(
        "user-agent", ""
    )
    logger.info(
        "internal_token_issued",
        user_id=user.id,
        telegram_id=body.telegram_id,
        scope=INTERNAL_TOKEN_SCOPE,
        ttl_min=INTERNAL_TOKEN_TTL_MIN,
        ip=client_ip,
        ua=user_agent[:80],
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        is_admin=False,
    )


if settings.debug:

    @router.post(
        "/mock/{user_id}",
        response_model=TokenResponse,
    )
    async def auth_mock(
        request: Request,
        user_id: int,
        session: AsyncSession = Depends(get_db),
    ) -> TokenResponse:
        service = UserService(session)
        user = await service.get_by_id(user_id)
        if not user:
            user_data = UserCreate(
                telegram_id=user_id,
                username=f"mockuser_{user_id}",
                first_name="Mock",
                last_name="Tester",
            )
            user, _ = (
                await service.register_or_update(
                    user_data
                )
            )

        token = create_access_token(
            user.id, user.is_admin
        )
        logger.warning(
            "mock_auth_used", user_id=user.id
        )
        return TokenResponse(
            access_token=token,
            user_id=user.id,
            is_admin=user.is_admin,
        )
