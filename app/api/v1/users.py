import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_db
from app.schemas.user import UserCreate, UserResponse, UserStatsResponse
from app.services.stats_service import StatsService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Register or update a user by Telegram ID",
)
@limiter.limit("60/minute")
async def register_or_update_user(
    request: Request,
    data: UserCreate,
    session: AsyncSession = Depends(get_db),
) -> UserResponse:
    structlog.contextvars.bind_contextvars(
        telegram_id=data.telegram_id
    )
    service = UserService(session)
    user, created = await service.register_or_update(data)
    status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    logger.info(
        "user_endpoint_response",
        user_id=user.id,
        created=created,
        status_code=status_code,
    )
    return UserResponse.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user profile by internal ID",
)
@limiter.limit("120/minute")
async def get_user(
    request: Request,
    user_id: int,
    session: AsyncSession = Depends(get_db),
) -> UserResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    service = UserService(session)
    user = await service.get_by_id(user_id)
    if not user:
        logger.warning("user_not_found_endpoint", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


@router.get(
    "/{user_id}/stats",
    response_model=UserStatsResponse,
    summary="Get author analytics for a user",
)
@limiter.limit("60/minute")
async def get_user_stats(
    request: Request,
    user_id: int,
    session: AsyncSession = Depends(get_db),
) -> UserStatsResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    service = StatsService(session)
    stats = await service.get_author_stats(user_id)
    logger.info(
        "stats_endpoint_response",
        user_id=user_id,
        total_tracks=stats.total_tracks,
        total_plays=stats.total_plays,
    )
    return stats
