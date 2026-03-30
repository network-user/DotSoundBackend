import mimetypes

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.user import (
    AvatarResponse,
    UserCreate,
    UserResponse,
    UserStatsResponse,
    UserUpdateRequest,
)
from app.services.stats_service import StatsService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_ALLOWED_AVATAR_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
_MAX_AVATAR_BYTES = 2 * 1024 * 1024


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


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update own display name",
)
@limiter.limit("30/minute")
async def update_me(
    request: Request,
    data: UserUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    structlog.contextvars.bind_contextvars(user_id=current_user.id)
    if not data.display_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    service = UserService(session)
    user = await service.update_display_name(
        current_user.id, data.display_name
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


@router.post(
    "/me/avatar",
    response_model=AvatarResponse,
    summary="Upload own avatar",
)
@limiter.limit("10/minute")
async def upload_my_avatar(
    request: Request,
    avatar: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AvatarResponse:
    structlog.contextvars.bind_contextvars(user_id=current_user.id)
    mime = avatar.content_type or ""
    if not mime or mime == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(avatar.filename or "")
        mime = guessed or mime
    if mime not in _ALLOWED_AVATAR_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Avatar must be JPEG, PNG, or WebP",
        )
    data = await avatar.read()
    if len(data) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Avatar exceeds 2 MB limit",
        )
    avatar_key = await s3.upload_avatar(
        data=data, content_type=mime, user_id=current_user.id
    )
    service = UserService(session)
    await service.update_avatar_key(current_user.id, avatar_key)
    avatar_url = await s3.get_presigned_url(avatar_key)
    logger.info(
        "avatar_uploaded",
        user_id=current_user.id,
        avatar_key=avatar_key,
    )
    return AvatarResponse(avatar_url=avatar_url)


@router.get(
    "/{user_id}/avatar",
    response_model=AvatarResponse,
    summary="Get presigned URL for user avatar",
)
@limiter.limit("120/minute")
async def get_avatar(
    request: Request,
    user_id: int,
    session: AsyncSession = Depends(get_db),
) -> AvatarResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    service = UserService(session)
    user = await service.get_by_id(user_id)
    if not user or not user.avatar_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom avatar not found",
        )
    avatar_url = await s3.get_presigned_url(user.avatar_key)
    return AvatarResponse(avatar_url=avatar_url)


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
