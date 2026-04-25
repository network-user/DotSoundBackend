from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.recommendation import (
    RecommendationRepository,
)
from app.schemas.recommendation import (
    DailyMixResponse,
    DailyPlaylistResponse,
    HomePageResponse,
    HomeSectionResponse,
    RadioQueueResponse,
    SimilarTracksResponse,
    WeeklyPlaylistResponse,
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


@router.get(
    "/daily-playlist",
    response_model=DailyPlaylistResponse,
)
async def get_daily_playlist(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RecommendationService(db)
    payload = await svc.get_daily_playlist(user.id)
    repo = RecommendationRepository(db)
    internal = await repo.get_tracks_by_ids(
        payload.get("internal_track_ids", [])
    )
    external = await repo.get_tracks_by_ids(
        payload.get("external_track_ids", [])
    )
    global_top = await repo.get_tracks_by_ids(
        payload.get("global_top_ids", [])
    )
    return DailyPlaylistResponse(
        internal_tracks=[
            TrackResponse.model_validate(t)
            for t in internal
        ],
        external_tracks=[
            TrackResponse.model_validate(t)
            for t in external
        ],
        global_top=[
            TrackResponse.model_validate(t)
            for t in global_top
        ],
        generated_at=payload["generated_at"],
        expires_at=payload["expires_at"],
    )


@router.get(
    "/weekly-playlist",
    response_model=WeeklyPlaylistResponse,
)
async def get_weekly_playlist(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RecommendationService(db)
    payload = await svc.get_weekly_playlist(user.id)
    repo = RecommendationRepository(db)
    internal = await repo.get_tracks_by_ids(
        payload.get("internal_track_ids", [])
    )
    external = await repo.get_tracks_by_ids(
        payload.get("external_track_ids", [])
    )
    return WeeklyPlaylistResponse(
        internal_tracks=[
            TrackResponse.model_validate(t)
            for t in internal
        ],
        external_tracks=[
            TrackResponse.model_validate(t)
            for t in external
        ],
        generated_at=payload["generated_at"],
        expires_at=payload["expires_at"],
    )


@router.post(
    "/daily-playlist/refresh",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def refresh_daily_playlist(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only",
        )
    svc = RecommendationService(db)
    await svc.refresh_daily_playlist(user.id)
