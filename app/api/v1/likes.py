import structlog
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.like import LikeToggleResponse, UserLikesResponse
from app.schemas.track import TrackResponse
from app.services.like_service import LikeService

router = APIRouter(prefix="/likes", tags=["likes"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.post(
    "/{track_id}",
    response_model=LikeToggleResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle like on a track (authenticated)",
)
@limiter.limit("60/minute")
async def toggle_like(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LikeToggleResponse:
    structlog.contextvars.bind_contextvars(
        user_id=current_user.id, track_id=track_id
    )
    service = LikeService(session)
    liked = await service.toggle(current_user.id, track_id)
    logger.info("like_toggle_endpoint", liked=liked)
    return LikeToggleResponse(track_id=track_id, liked=liked)


@router.post(
    "/{user_id}/{track_id}",
    response_model=LikeToggleResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle like on a track (internal / bot)",
)
@limiter.limit("60/minute")
async def toggle_like_public(
    request: Request,
    user_id: int,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LikeToggleResponse:
    structlog.contextvars.bind_contextvars(
        user_id=user_id, track_id=track_id
    )
    service = LikeService(session)
    liked = await service.toggle(user_id, track_id)
    logger.info("like_toggle_endpoint_public", liked=liked)
    return LikeToggleResponse(track_id=track_id, liked=liked)


@router.get(
    "/{user_id}",
    response_model=UserLikesResponse,
    summary="Get tracks liked by a user",
)
@limiter.limit("120/minute")
async def get_user_likes(
    request: Request,
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
) -> UserLikesResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    service = LikeService(session)
    tracks, total = await service.list_liked(
        user_id=user_id, page=page, size=size
    )
    return UserLikesResponse(
        items=[TrackResponse.model_validate(t) for t in tracks],
        total=total,
        page=page,
        has_more=(page * size) < total,
    )
