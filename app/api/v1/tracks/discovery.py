"""Track discovery endpoints — public listing, search, and cover proxy."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_db
from app.schemas.track import TrackListResponse, TrackResponse
from app.services.track_service import TrackService

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.get(
    "/",
    response_model=TrackListResponse,
    summary="List active tracks with optional search",
)
@limiter.limit("200/minute")
async def list_tracks(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
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
    "/cover_proxy",
    summary="Redirect to presigned cover URL by MinIO key",
)
@limiter.limit("600/minute")
async def cover_proxy(
    request: Request,
    key: str = Query(..., description="MinIO object key"),
) -> RedirectResponse:
    if ".." in key or key.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid key",
        )
    url = await s3.get_presigned_url(key)
    return RedirectResponse(url=url, status_code=302)
