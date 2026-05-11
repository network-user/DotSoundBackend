from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.track import BCSearchResult, TrackResponse
from app.services.bandcamp_service import BandcampService
from app.services.track_response_build import build_track_response

router = APIRouter(prefix="/bandcamp", tags=["bandcamp"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class BCImportRequest(BaseModel):
    bc_url: str
    is_public: bool = True


@router.get(
    "/search",
    response_model=list[BCSearchResult],
    summary="Search tracks on Bandcamp (public preview list)",
)
@limiter.limit("20/minute")
async def search_bandcamp(
    request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=20),
    session: AsyncSession = Depends(get_db),
) -> list[BCSearchResult]:
    service = BandcampService(session)
    rows = await service.search(q, limit=limit)
    return [BCSearchResult(**r) for r in rows]


@router.post(
    "/import",
    response_model=TrackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import a Bandcamp track by URL (authenticated)",
)
@limiter.limit("20/minute")
async def import_bandcamp_track(
    request: Request,
    data: BCImportRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackResponse:
    structlog.contextvars.bind_contextvars(bc_url=data.bc_url)

    try:
        parsed = urlparse(data.bc_url)
    except ValueError:
        parsed = None
    host = (parsed.hostname or "").lower() if parsed else ""
    if parsed is None or parsed.scheme not in ("http", "https") or not (
        host == "bandcamp.com" or host.endswith(".bandcamp.com")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must be a link to a track on bandcamp.com.",
        )

    service = BandcampService(session)
    bc_data = await service.resolve_url(data.bc_url)

    track = await service.import_or_get_track(
        bc_data=bc_data,
        uploader_id=current_user.id,
        is_public=data.is_public,
    )
    logger.info(
        "bc_import_endpoint",
        track_id=track.id,
    )
    return await build_track_response(session, track)
