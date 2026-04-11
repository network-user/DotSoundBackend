import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_db
from app.schemas.track import (
    TrackListResponse,
    TrackResponse,
)
from app.services.track_service import TrackService

router = APIRouter()
logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


@router.get(
    "/",
    response_model=TrackListResponse,
)
@limiter.limit("200/minute")
async def list_tracks(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
) -> TrackListResponse:
    service = TrackService(session)
    if q:
        structlog.contextvars.bind_contextvars(
            search_query=q
        )
        tracks, total = await service.search(
            q, page=page, size=size
        )
    else:
        tracks, total = await service.list_tracks(
            page=page, size=size
        )
    return TrackListResponse(
        items=[
            TrackResponse.model_validate(t)
            for t in tracks
        ],
        total=total,
        page=page,
        size=size,
    )


@router.get("/cover_proxy")
@limiter.limit("600/minute")
async def cover_proxy(
    request: Request,
    key: str = Query(...),
) -> Response:
    _ALLOWED_PREFIXES = (
        "covers/", "avatars/",
    )
    if (
        ".." in key
        or key.startswith("/")
        or not key.startswith(_ALLOWED_PREFIXES)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid key",
        )
    try:
        data = await s3.download_object(key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cover not found",
        )
    content_type = "image/png"
    if key.endswith(".jpg") or key.endswith(".jpeg"):
        content_type = "image/jpeg"
    elif key.endswith(".webp"):
        content_type = "image/webp"
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/genres",
    response_model=list[str],
    summary="Get a list of unique track genres currently in the database",
)
@limiter.limit("60/minute")
async def get_genres(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> list[str]:
    service = TrackService(session)
    return await service.get_genres()
