from datetime import UTC, datetime

from dotsound_private_core.services.playcount_policy import (
    USER_CHOICE_SCORE_VERSION,
)
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
    GenreMixItemResponse,
    GenreMixesResponse,
    GenreMixOverrideRequest,
    HomePageResponse,
    HomeSectionResponse,
    RadioQueueResponse,
    SimilarTracksResponse,
    UserChoicePlaylistResponse,
    WeeklyPlaylistResponse,
)
from app.services.recommendation_service import (
    RecommendationService,
)
from app.services.track_response_build import (
    dedupe_and_build_track_list,
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
    
    sections = []
    for s in data["sections"]:
        tracks_out = await dedupe_and_build_track_list(db, s["tracks"])
        sections.append(
            HomeSectionResponse(
                title=s["title"],
                section_type=s["section_type"],
                tracks=tracks_out,
            )
        )
        
    highlights = []
    for h in data.get("highlights", []):
        track_out = await dedupe_and_build_track_list(db, [h["track"]])
        if track_out:
            highlights.append(
                {
                    "track": track_out[0],
                    "label": h["label"],
                    "reason": h.get("reason"),
                    "hero_image_key": h.get("hero_image_key"),
                }
            )
            
    return HomePageResponse(
        sections=sections,
        highlights=highlights,
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
        tracks=await dedupe_and_build_track_list(db, tracks),
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
        tracks=await dedupe_and_build_track_list(db, tracks),
        generated_at=datetime.now(
            UTC
        ).isoformat(),
    )


@router.get(
    "/genre-mixes",
    response_model=GenreMixesResponse,
)
async def get_genre_mixes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RecommendationService(db)
    mixes = await svc.get_genre_mixes(user.id)
    result = []
    for mix in mixes:
        tracks_out = await dedupe_and_build_track_list(
            db, mix["tracks"]
        )
        result.append(
            GenreMixItemResponse(
                genre=mix["genre"],
                title=mix["title"],
                tracks=tracks_out,
            )
        )
    return GenreMixesResponse(mixes=result)


@router.put(
    "/genre-mixes/{genre}",
    response_model=GenreMixItemResponse,
)
async def save_genre_mix_override(
    genre: str,
    body: GenreMixOverrideRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only",
        )
    svc = RecommendationService(db)
    try:
        saved = await svc.save_genre_mix_override(
            genre=genre,
            title=body.title,
            track_ids=body.track_ids,
            updated_by_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    tracks_out = await dedupe_and_build_track_list(
        db, saved["tracks"]
    )
    return GenreMixItemResponse(
        genre=saved["genre"],
        title=saved["title"],
        tracks=tracks_out,
    )


@router.get(
    "/radio", response_model=RadioQueueResponse
)
async def get_radio(
    seed_track_id: int = Query(...),
    queue_size: int = Query(default=20, le=50),
    exclude_ids: str = Query(default=""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exclude: list[int] = []
    if exclude_ids:
        try:
            exclude = [
                int(x)
                for x in exclude_ids.split(",")
                if x.strip()
            ][:30]
        except ValueError:
            exclude = []
    svc = RecommendationService(db)
    tracks = await svc.get_radio(
        seed_track_id=seed_track_id,
        queue_size=queue_size,
        user_id=user.id,
        exclude_ids=exclude,
    )
    return RadioQueueResponse(
        seed_type="track",
        seed_id=str(seed_track_id),
        tracks=await dedupe_and_build_track_list(db, tracks),
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
        internal_tracks=await dedupe_and_build_track_list(db, internal),
        external_tracks=await dedupe_and_build_track_list(db, external),
        global_top=await dedupe_and_build_track_list(db, global_top),
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
        internal_tracks=await dedupe_and_build_track_list(db, internal),
        external_tracks=await dedupe_and_build_track_list(db, external),
        generated_at=payload["generated_at"],
        expires_at=payload["expires_at"],
    )


@router.get(
    "/user-choice",
    response_model=UserChoicePlaylistResponse,
)
async def get_user_choice_playlist(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(
        default=100, ge=1, le=200
    ),
):
    svc = RecommendationService(db)
    tracks = await svc.get_user_choice_playlist(
        limit=limit
    )
    return UserChoicePlaylistResponse(
        tracks=await dedupe_and_build_track_list(db, tracks),
        generated_at=datetime.now(UTC).isoformat(),
        score_version=USER_CHOICE_SCORE_VERSION,
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
