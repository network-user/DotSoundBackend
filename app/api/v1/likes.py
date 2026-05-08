import structlog
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.like import (
    LikedTrackResponse,
    LikeToggleResponse,
    UserLikesResponse,
)
from app.services.like_service import LikeService
from app.services.track_response_build import build_track_response

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
    liked, variant_ids = await service.toggle(current_user.id, track_id)
    logger.info("like_toggle_endpoint", liked=liked)
    return LikeToggleResponse(
        track_id=track_id,
        liked=liked,
        playback_variant_track_ids=variant_ids,
    )


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
    liked, variant_ids = await service.toggle(user_id, track_id)
    logger.info("like_toggle_endpoint_public", liked=liked)
    return LikeToggleResponse(
        track_id=track_id,
        liked=liked,
        playback_variant_track_ids=variant_ids,
    )


_VALID_SOURCE_FILTERS = frozenset(
    {"platform", "soundcloud", "other"}
)


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
    source: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
) -> UserLikesResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    source_filter = (
        source if source in _VALID_SOURCE_FILTERS else None
    )
    service = LikeService(session)
    rows, total = await service.list_liked(
        user_id=user_id,
        page=page,
        size=size,
        source_filter=source_filter,
    )
    items = []
    for track, liked_at in rows:
        tr = await build_track_response(session, track)
        items.append(
            LikedTrackResponse(
                **tr.model_dump(),
                liked_at=liked_at,
            )
        )
    return UserLikesResponse(
        items=items,
        total=total,
        page=page,
        has_more=(page * size) < total,
    )
