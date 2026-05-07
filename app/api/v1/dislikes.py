import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.like import (
    DislikedTrackResponse,
    DislikeToggleResponse,
    UserDislikesResponse,
)
from app.services.dislike_service import DislikeService
from app.services.track_response_build import build_track_response

router = APIRouter(prefix="/dislikes", tags=["dislikes"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_VALID_SOURCE_FILTERS = frozenset({"platform", "soundcloud", "other"})


@router.get(
    "/{user_id}",
    response_model=UserDislikesResponse,
    summary="List disliked tracks for the authenticated user",
)
@limiter.limit("120/minute")
async def get_user_dislikes(
    request: Request,
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    source: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserDislikesResponse:
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
    structlog.contextvars.bind_contextvars(user_id=user_id)
    source_filter = source if source in _VALID_SOURCE_FILTERS else None
    service = DislikeService(session)
    rows, total = await service.list_disliked(
        user_id=user_id,
        page=page,
        size=size,
        source_filter=source_filter,
    )
    items = []
    for track, disliked_at in rows:
        tr = await build_track_response(session, track)
        items.append(
            DislikedTrackResponse(
                **tr.model_dump(),
                disliked_at=disliked_at,
            )
        )
    return UserDislikesResponse(
        items=items,
        total=total,
        page=page,
        has_more=(page * size) < total,
    )


@router.post(
    "/{track_id}",
    response_model=DislikeToggleResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle dislike on a track (authenticated)",
)
@limiter.limit("60/minute")
async def toggle_dislike(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DislikeToggleResponse:
    structlog.contextvars.bind_contextvars(
        user_id=current_user.id, track_id=track_id
    )
    service = DislikeService(session)
    disliked, variant_ids = await service.toggle(current_user.id, track_id)
    logger.info("dislike_toggle_endpoint", disliked=disliked)
    return DislikeToggleResponse(
        track_id=track_id,
        disliked=disliked,
        playback_variant_track_ids=variant_ids,
    )


@router.post(
    "/{user_id}/{track_id}",
    response_model=DislikeToggleResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle dislike on a track (internal / bot)",
)
@limiter.limit("60/minute")
async def toggle_dislike_public(
    request: Request,
    user_id: int,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DislikeToggleResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id, track_id=track_id)
    service = DislikeService(session)
    disliked, variant_ids = await service.toggle(user_id, track_id)
    logger.info("dislike_toggle_endpoint_public", disliked=disliked)
    return DislikeToggleResponse(
        track_id=track_id,
        disliked=disliked,
        playback_variant_track_ids=variant_ids,
    )
