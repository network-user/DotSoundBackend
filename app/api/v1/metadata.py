import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.track import Track

router = APIRouter(prefix="/metadata", tags=["metadata"])
logger = structlog.stdlib.get_logger(__name__)


@router.get(
    "/genres",
    response_model=list[str],
    summary="Get a list of popular genres used in the platform",
)
async def get_popular_genres(
    session: AsyncSession = Depends(get_db),
    limit: int = 50,
) -> list[str]:
    from sqlalchemy import func
    result = await session.execute(
        select(Track.genre)
        .where(Track.genre.is_not(None))
        .group_by(Track.genre)
        .order_by(func.count(Track.id).desc())
        .limit(limit)
    )
    return list(result.scalars().all())
