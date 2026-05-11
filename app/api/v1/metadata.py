import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.track import TrackRepository

router = APIRouter(prefix="/metadata", tags=["metadata"])
logger = structlog.stdlib.get_logger(__name__)


@router.get(
    "/genres",
    response_model=list[str],
    summary="Get a list of popular genres used in the platform",
)
async def get_popular_genres(
    session: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
) -> list[str]:
    repo = TrackRepository(session)
    return await repo.list_popular_genres(limit=limit)
