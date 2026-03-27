import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_db
from app.schemas.track import TrackListResponse, TrackResponse
from app.services.track_service import TrackService

router = APIRouter(prefix="/tracks", tags=["tracks"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.get(
    "",
    response_model=TrackListResponse,
    summary="List active tracks with pagination",
)
@limiter.limit("200/minute")
async def list_tracks(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    q: str | None = Query(None, description="Search query"),
    session: AsyncSession = Depends(get_db),
) -> TrackListResponse:
    service = TrackService(session)
    if q:
        structlog.contextvars.bind_contextvars(search_query=q)
        tracks, total = await service.search(q, page=page, size=size)
    else:
        tracks, total = await service.list_tracks(page=page, size=size)
    return TrackListResponse(
        items=[TrackResponse.model_validate(t) for t in tracks],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{track_id}",
    response_model=TrackResponse,
    summary="Get a single track by ID",
)
@limiter.limit("300/minute")
async def get_track(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
) -> TrackResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.get_track(track_id)
    if not track:
        logger.warning(
            "track_not_found_endpoint", track_id=track_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    return TrackResponse.model_validate(track)
