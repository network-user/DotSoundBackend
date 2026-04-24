import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.track import TrackResponse
from app.services.bandcamp_service import BandcampService

router = APIRouter(prefix="/bandcamp", tags=["bandcamp"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class BCImportRequest(BaseModel):
    bc_url: str
    is_public: bool = True


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

    if "bandcamp.com" not in data.bc_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL должен быть ссылкой на трек с bandcamp.com.",
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
    return TrackResponse.model_validate(track)
