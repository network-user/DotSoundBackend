import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.track import TrackResponse, YTSearchResult
from app.services.youtube_service import YouTubeService, _extract_video_id

router = APIRouter(prefix="/youtube", tags=["youtube"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class YTImportRequest(BaseModel):
    yt_url: str
    is_public: bool = True


@router.get(
    "/search",
    response_model=list[YTSearchResult],
    summary="Search videos on YouTube (public preview list)",
)
@limiter.limit("20/minute")
async def search_youtube(
    request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=20),
    session: AsyncSession = Depends(get_db),
) -> list[YTSearchResult]:
    service = YouTubeService(session)
    rows = await service.search(q, limit=limit)
    return [YTSearchResult(**r) for r in rows]


@router.post(
    "/import",
    response_model=TrackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import a YouTube track by URL (authenticated)",
)
@limiter.limit("10/minute")
async def import_youtube_track(
    request: Request,
    data: YTImportRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackResponse:
    structlog.contextvars.bind_contextvars(yt_url=data.yt_url)

    video_id = _extract_video_id(data.yt_url)
    if not video_id:
        if "youtube.com" not in data.yt_url and "youtu.be" not in data.yt_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL должен быть ссылкой на YouTube-видео "
                "(youtube.com или youtu.be).",
            )

    service = YouTubeService(session)
    yt_data = await service.resolve_url(data.yt_url)

    if yt_data.get("_type") in ("playlist", "multi_video"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вставьте ссылку на конкретное видео, а не плейлист.",
        )

    track = await service.import_or_get_track(
        yt_data=yt_data,
        uploader_id=current_user.id,
        is_public=data.is_public,
    )
    logger.info(
        "yt_import_endpoint",
        track_id=track.id,
    )
    return TrackResponse.model_validate(track)
