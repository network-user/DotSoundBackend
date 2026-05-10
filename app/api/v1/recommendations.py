from datetime import UTC, datetime

from dotsound_private_core.services.playcount_policy import (
    USER_CHOICE_SCORE_VERSION,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, get_optional_user
from app.models.user import User
from app.repositories.artist import ArtistRepository
from app.repositories.recommendation import (
    RecommendationRepository,
)
from app.repositories.signal import (
    ListenEventRepository,
)
from app.schemas.artist import ArtistResponse
from app.schemas.recommendation import (
    DailyMixResponse,
    DailyPlaylistResponse,
    DiscoverGenreCard,
    DiscoverResponse,
    ForgottenTreasuresPlaylistResponse,
    GenreMixesResponse,
    GenreMixItemResponse,
    GenreMixOverrideRequest,
    HomePageResponse,
    HomeSectionResponse,
    RadioQueueResponse,
    SimilarTracksResponse,
    UserChoicePlaylistResponse,
    WeeklyPlaylistResponse,
    WeeklyTopPlaylistResponse,
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
    listen_repo = ListenEventRepository(db)
    for s in data["sections"]:
        tracks_out = await dedupe_and_build_track_list(db, s["tracks"])
        if s["section_type"] == "continue" and tracks_out:
            positions = await listen_repo.latest_resume_position(
                user.id, [t.id for t in tracks_out]
            )
            if positions:
                tracks_out = [
                    t.model_copy(
                        update={
                            "resume_position_seconds": positions.get(
                                t.id
                            )
                        }
                    )
                    if positions.get(t.id) is not None
                    else t
                    for t in tracks_out
                ]
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


@router.get(
    "/genre-mixes/{genre}",
    response_model=GenreMixItemResponse,
)
async def get_genre_mix(
    genre: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RecommendationService(db)
    mix = await svc.get_genre_mix(
        user_id=user.id,
        genre=genre,
    )
    if mix is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="genre mix not found",
        )
    tracks_out = await dedupe_and_build_track_list(
        db, mix["tracks"]
    )
    return GenreMixItemResponse(
        genre=mix["genre"],
        title=mix["title"],
        tracks=tracks_out,
    )


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
            ][:200]
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


@router.get(
    "/weekly-top",
    response_model=WeeklyTopPlaylistResponse,
)
async def get_weekly_top_playlist(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
):
    svc = RecommendationService(db)
    payload = await svc.get_weekly_top_playlist(
        limit=limit
    )
    repo = RecommendationRepository(db)
    tracks = await repo.get_tracks_by_ids(
        payload.get("track_ids", [])
    )
    return WeeklyTopPlaylistResponse(
        tracks=await dedupe_and_build_track_list(db, tracks),
        generated_at=payload["generated_at"],
        expires_at=payload["expires_at"],
        score_version=payload["score_version"],
        window_days=payload["window_days"],
    )


@router.get(
    "/forgotten-treasures",
    response_model=ForgottenTreasuresPlaylistResponse,
)
async def get_forgotten_treasures_playlist(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
):
    svc = RecommendationService(db)
    payload = await svc.get_forgotten_treasures_playlist(
        user.id,
        limit=limit,
    )
    repo = RecommendationRepository(db)
    tracks = await repo.get_tracks_by_ids(
        payload["track_ids"]
    )
    return ForgottenTreasuresPlaylistResponse(
        tracks=await dedupe_and_build_track_list(db, tracks),
        generated_at=payload["generated_at"],
        expires_at=payload["expires_at"],
        score_version=payload["score_version"],
        min_like_age_days=payload["min_like_age_days"],
        silence_days=payload["silence_days"],
    )


@router.get(
    "/home-highlight",
    summary=(
        "Pick a single hero track for the Mini App home screen "
        "(weekly_top / your_top / forgotten_treasures / "
        "personalized) with stable per-user TTL"
    ),
)
async def get_home_highlight(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object] | None:
    from app.services.home_highlight_service import (
        HomeHighlightService,
    )

    svc = HomeHighlightService(db)
    payload = await svc.get_for_user(user.id)
    return payload


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


@router.get(
    "/discover",
    response_model=DiscoverResponse,
    summary="Personalized discover page for search empty state",
)
async def get_discover(
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    trending_limit: int = Query(default=10, ge=1, le=20),
    artist_limit: int = Query(default=8, ge=1, le=20),
) -> DiscoverResponse:
    from sqlalchemy import desc, func, select  # noqa: PLC0415

    from app.models.track import Track as TrackModel  # noqa: PLC0415

    rec_repo = RecommendationRepository(db)
    artist_repo = ArtistRepository(db)

    trending_raw = await rec_repo.get_popular_tracks(limit=trending_limit)
    trending_out = await dedupe_and_build_track_list(db, trending_raw)

    artists_raw = await artist_repo.list_popular(limit=artist_limit)
    artists_out = [
        ArtistResponse.model_validate(a) for a in artists_raw
    ]

    genre_ranked = (
        select(
            TrackModel.genre.label("genre"),
            TrackModel.cover_key.label("cover_key"),
            func.count(TrackModel.id)
            .over(partition_by=TrackModel.genre)
            .label("cnt"),
            func.row_number()
            .over(
                partition_by=TrackModel.genre,
                order_by=(
                    TrackModel.play_count.desc(),
                    TrackModel.id.desc(),
                ),
            )
            .label("rn"),
        )
        .where(
            TrackModel.genre.isnot(None),
            TrackModel.genre != "",
            TrackModel.is_active.is_(True),
            TrackModel.is_public.is_(True),
        )
        .subquery()
    )
    genre_rows = await db.execute(
        select(
            genre_ranked.c.genre,
            genre_ranked.c.cnt,
            genre_ranked.c.cover_key,
        )
        .where(genre_ranked.c.rn == 1)
        .order_by(desc(genre_ranked.c.cnt))
        .limit(12)
    )
    genre_cards = [
        DiscoverGenreCard(
            genre=str(row[0]),
            title=str(row[0]),
            track_count=int(row[1]),
            cover_key=str(row[2]) if row[2] else None,
        )
        for row in genre_rows.all()
    ]

    recent_genres: list[str] = []
    if user:
        listen_repo = ListenEventRepository(db)
        recent_events = await listen_repo.get_recent(user.id, limit=40)
        if recent_events:
            recent_track_ids = list(
                dict.fromkeys(e.track_id for e in recent_events)
            )[:30]
            recent_tracks_raw = await rec_repo.get_tracks_by_ids(
                recent_track_ids
            )
            seen: set[str] = set()
            for t in recent_tracks_raw:
                if t.genre and t.genre not in seen:
                    seen.add(t.genre)
                    recent_genres.append(t.genre)
                    if len(recent_genres) >= 5:
                        break

    return DiscoverResponse(
        trending_tracks=trending_out,
        suggested_artists=artists_out,
        genre_cards=genre_cards,
        recent_genres=recent_genres,
    )
