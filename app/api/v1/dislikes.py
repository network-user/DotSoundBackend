import structlog
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.like import DislikeToggleResponse
from app.services.dislike_service import DislikeService

router = APIRouter(prefix="/dislikes", tags=["dislikes"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


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
    disliked = await service.toggle(current_user.id, track_id)
    logger.info("dislike_toggle_endpoint", disliked=disliked)
    return DislikeToggleResponse(track_id=track_id, disliked=disliked)
