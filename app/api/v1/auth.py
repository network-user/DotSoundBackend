import random
import string
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
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

_CODE_TTL = 300
_CODE_PREFIX = "auth_code:"

_redis_client: Any = None


async def _get_redis() -> Any:
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as aioredis

        _redis_client = aioredis.from_url(
            settings.redis_url
        )
    return _redis_client


def _generate_code() -> str:
    return "".join(
        random.choices(string.digits, k=6)
    )


def _mask_ip(ip: str) -> str:
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.***.***.{parts[3]}"
    return ip[:4] + "***"


def _parse_user_agent(ua: str) -> str:
    ua_lower = ua.lower()
    browser = "Unknown"
    os_name = "Unknown"

    if (
        "chrome" in ua_lower
        and "edg" not in ua_lower
    ):
        browser = "Chrome"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    elif (
        "safari" in ua_lower
        and "chrome" not in ua_lower
    ):
        browser = "Safari"
    elif "edg" in ua_lower:
        browser = "Edge"

    if "windows" in ua_lower:
        os_name = "Windows"
    elif (
        "macintosh" in ua_lower
        or "mac os" in ua_lower
    ):
        os_name = "macOS"
    elif "android" in ua_lower:
        os_name = "Android"
    elif (
        "iphone" in ua_lower
        or "ipad" in ua_lower
    ):
        os_name = "iOS"
    elif "linux" in ua_lower:
        os_name = "Linux"

    return f"{browser}, {os_name}"


def _bot_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if settings.bot_internal_secret:
        headers["X-Internal-Secret"] = (
            settings.bot_internal_secret
        )
    return headers


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
    expires_in: int = _CODE_TTL


@router.post(
    "/generate-code",
    response_model=GenerateCodeResponse,
)
async def generate_auth_code(
    request: Request,
    body: GenerateCodeRequest,
) -> GenerateCodeResponse:
    secret = request.headers.get(
        "X-Internal-Secret", ""
    )
    if (
        settings.bot_internal_secret
        and secret != settings.bot_internal_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    code = _generate_code()
    redis = await _get_redis()
    await redis.setex(
        f"{_CODE_PREFIX}{code}",
        _CODE_TTL,
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
@limiter.limit("10/minute")
async def verify_telegram_code(
    request: Request,
    body: CodeVerifyRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    redis = await _get_redis()
    key = f"{_CODE_PREFIX}{body.code}"
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
                f"{settings.bot_internal_url}"
                "/internal/send-login-notification",
                headers=_bot_headers(),
                json={
                    "telegram_id": telegram_id,
                    "ip": _mask_ip(client_ip),
                    "device": _parse_user_agent(
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
            ip=_mask_ip(client_ip),
            device=_parse_user_agent(user_agent),
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
