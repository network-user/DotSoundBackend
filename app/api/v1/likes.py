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
    LikedTrackResponse,
    LikeToggleResponse,
    UserLikesResponse,
)
from app.schemas.track import TrackQueueResponse
from app.services.like_service import LikeService
from app.services.track_response_build import (
    build_track_response,
    build_track_responses,
)

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
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
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
_VALID_SORT_ORDERS = frozenset({"newest", "oldest", "artist"})


def _source_filter_or_none(source: str | None) -> str | None:
    return source if source in _VALID_SOURCE_FILTERS else None


def _sort_order_or_default(sort: str | None) -> str:
    return sort if sort in _VALID_SORT_ORDERS else "newest"


def _parse_exclude_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    result: set[int] = set()
    for part in raw.split(","):
        if len(result) >= 300:
            break
        try:
            value = int(part)
        except ValueError:
            continue
        if value > 0:
            result.add(value)
    return result


@router.get(
    "/{user_id}/queue",
    response_model=TrackQueueResponse,
    summary="Get a liked-track playback queue",
)
@limiter.limit("120/minute")
async def get_user_likes_queue(
    request: Request,
    user_id: int,
    current_track_id: int = Query(..., ge=1),
    size: int = Query(80, ge=1, le=100),
    source: str | None = Query(None),
    sort: str = Query("newest"),
    shuffle: bool = Query(False),
    exclude_ids: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
) -> TrackQueueResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    service = LikeService(session)
    tracks = await service.list_liked_queue(
        user_id=user_id,
        current_track_id=current_track_id,
        size=size,
        source_filter=_source_filter_or_none(source),
        sort_order=_sort_order_or_default(sort),
        shuffle=shuffle,
        exclude_ids=_parse_exclude_ids(exclude_ids),
    )
    return TrackQueueResponse(
        next_tracks=await build_track_responses(session, tracks),
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
    sort: str = Query("newest"),
    session: AsyncSession = Depends(get_db),
) -> UserLikesResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    service = LikeService(session)
    rows, total = await service.list_liked(
        user_id=user_id,
        page=page,
        size=size,
        source_filter=_source_filter_or_none(source),
        sort_order=_sort_order_or_default(sort),
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
