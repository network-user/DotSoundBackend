import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import AuthError, create_access_token, verify_telegram_init_data
from app.core.rate_limit import limiter
from app.dependencies import get_db
from app.schemas.auth import TelegramAuthRequest, TokenResponse
from app.schemas.user import UserCreate
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.post(
    "/telegram",
    response_model=TokenResponse,
    summary="Authenticate via Telegram WebApp initData",
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
            detail="Telegram auth is not configured (TELEGRAM_BOT_TOKEN missing)",
        )
    try:
        tg_user = verify_telegram_init_data(body.init_data)
    except AuthError as exc:
        logger.warning("telegram_auth_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    service = UserService(session)
    user_data = UserCreate(
        telegram_id=int(tg_user["id"]),  # type: ignore[arg-type]
        username=str(tg_user["username"]) if tg_user.get("username") else None,
        first_name=str(tg_user.get("first_name", "")),
        last_name=str(tg_user["last_name"]) if tg_user.get("last_name") else None,
    )
    user, created = await service.register_or_update(user_data)
    token = create_access_token(user.id, user.is_admin)
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


@router.post(
    "/mock/{user_id}",
    response_model=TokenResponse,
    summary="[DEV ONLY] Mock authentication for local testing",
)
async def auth_mock(
    request: Request,
    user_id: int,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Generate a JWT token for any user_id. 
    In production, this should be disabled or protected.
    """
    service = UserService(session)
    user = await service.get_by_id(user_id)
    if not user:
        # Create a mock user if not exists
        from app.schemas.user import UserCreate
        user_data = UserCreate(
            telegram_id=user_id,
            username=f"mockuser_{user_id}",
            first_name="Mock",
            last_name="Tester",
        )
        user, _ = await service.register_or_update(user_data)
    
    token = create_access_token(user.id, user.is_admin)
    logger.warning("mock_auth_used", user_id=user.id)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        is_admin=user.is_admin,
    )
