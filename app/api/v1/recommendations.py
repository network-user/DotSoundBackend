from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.recommendation import (
    DailyMixResponse,
    HomePageResponse,
    HomeSectionResponse,
    RadioQueueResponse,
    SimilarTracksResponse,
)
from app.schemas.track import TrackResponse
from app.services.recommendation_service import (
    RecommendationService,
)

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"],
)


@router.get(
    "/home", response_model=HomePageResponse
)
async def get_home(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RecommendationService(db)
    data = await svc.get_home_sections(user.id)
    sections = [
        HomeSectionResponse(
            title=s["title"],
            section_type=s["section_type"],
            tracks=[
                TrackResponse.model_validate(t)
                for t in s["tracks"]
            ],
        )
        for s in data["sections"]
    ]
    return HomePageResponse(
        sections=sections,
        maturity=data["maturity"],
    )


@router.get(
    "/similar/{track_id}",
    response_model=SimilarTracksResponse,
)
async def get_similar(
    track_id: int,
    limit: int = Query(default=10, le=30),
    db: AsyncSession = Depends(get_db),
):
    svc = RecommendationService(db)
    tracks = await svc.get_similar(
        track_id, limit
    )
    return SimilarTracksResponse(
        seed_track_id=track_id,
        tracks=[
            TrackResponse.model_validate(t)
            for t in tracks
        ],
    )


@router.get(
    "/daily-mix",
    response_model=DailyMixResponse,
)
async def get_daily_mix(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RecommendationService(db)
    tracks = await svc.get_daily_mix(user.id)
    return DailyMixResponse(
        tracks=[
            TrackResponse.model_validate(t)
            for t in tracks
        ],
        generated_at=datetime.now(
            UTC
        ).isoformat(),
    )


@router.get(
    "/radio", response_model=RadioQueueResponse
)
async def get_radio(
    seed_track_id: int = Query(...),
    queue_size: int = Query(default=20, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RecommendationService(db)
    tracks = await svc.get_radio(
        seed_track_id=seed_track_id,
        queue_size=queue_size,
        user_id=user.id,
    )
    return RadioQueueResponse(
        seed_type="track",
        seed_id=str(seed_track_id),
        tracks=[
            TrackResponse.model_validate(t)
            for t in tracks
        ],
    )
