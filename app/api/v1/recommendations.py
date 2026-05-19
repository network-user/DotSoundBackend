from datetime import UTC, datetime
from typing import Any

from dotsound_private_core.services.playcount_policy import (
    USER_CHOICE_SCORE_VERSION,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.core.redis import get_redis_client
from app.dependencies import get_current_user, get_db, get_optional_user
from app.models.track import Track
from app.models.user import User
from app.repositories.artist import ArtistRepository
from app.repositories.artist_stats import ArtistStatsRepository
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
from app.services.playback_variant_service import (
    PlaybackVariantService,
)
from app.services.recommendation_service import (
    RecommendationService,
)
from app.services.track_response_build import (
    build_track_responses,
    dedupe_and_build_track_list,
)

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"],
)


async def _home_section_response(
    db: AsyncSession,
    user_id: int,
    section: dict[str, Any],
) -> HomeSectionResponse:
    tracks_out = await dedupe_and_build_track_list(db, section["tracks"])
    if section["section_type"] == "continue" and tracks_out:
        positions = await ListenEventRepository(db).latest_resume_position(
            user_id, [t.id for t in tracks_out]
        )
        if positions:
            tracks_out = [
                (
                    t.model_copy(
                        update={
                            "resume_position_seconds": positions.get(t.id)
                        }
                    )
                    if positions.get(t.id) is not None
                    else t
                )
                for t in tracks_out
            ]
    return HomeSectionResponse(
        title=section["title"],
        section_type=section["section_type"],
        tracks=tracks_out,
    )


@router.get("/home", response_model=HomePageResponse)
async def get_home(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HomePageResponse:
    svc = RecommendationService(db)
    data = await svc.get_home_sections(user.id)

    sections = []
    for s in data["sections"]:
        sections.append(await _home_section_response(db, user.id, s))

    pvs = PlaybackVariantService(db)
    highlight_primaries: list[tuple[Track, dict[str, object]]] = []
    for h in data.get("highlights", []):
        deduped = await pvs.dedupe_track_rows_for_display([h["track"]])
        if deduped:
            highlight_primaries.append((deduped[0], h))
    unique_highlight_tracks: list[Track] = []
    seen_highlight_ids: set[int] = set()
    for t, _ in highlight_primaries:
        if t.id not in seen_highlight_ids:
            seen_highlight_ids.add(t.id)
            unique_highlight_tracks.append(t)
    highlight_responses = await build_track_responses(
        db, unique_highlight_tracks
    )
    highlight_response_by_id = {r.id: r for r in highlight_responses}
    highlights = []
    for t, h in highlight_primaries:
        resp = highlight_response_by_id.get(t.id)
        if resp is None:
            continue
        highlights.append(
            {
                "track": resp,
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
    "/home/sections/{section_type}",
    response_model=HomeSectionResponse,
)
async def get_home_section(
    section_type: str,
    limit: int = Query(default=15, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HomeSectionResponse:
    svc = RecommendationService(db)
    try:
        section = await svc.get_home_section(
            user.id,
            section_type=section_type,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Home section not found",
        ) from exc
    return await _home_section_response(db, user.id, section)


@router.get(
    "/similar/{track_id}",
    response_model=SimilarTracksResponse,
)
async def get_similar(
    track_id: int,
    limit: int = Query(default=10, le=30),
    db: AsyncSession = Depends(get_db),
) -> SimilarTracksResponse:
    svc = RecommendationService(db)
    tracks = await svc.get_similar(track_id, limit)
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
) -> DailyMixResponse:
    svc = RecommendationService(db)
    tracks = await svc.get_daily_mix(user.id)
    return DailyMixResponse(
        tracks=await dedupe_and_build_track_list(db, tracks),
        generated_at=datetime.now(UTC).isoformat(),
    )


@router.get(
    "/genre-mixes",
    response_model=GenreMixesResponse,
)
async def get_genre_mixes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenreMixesResponse:
    svc = RecommendationService(db)
    mixes = await svc.get_genre_mixes(user.id)
    result = []
    for mix in mixes:
        tracks_out = await dedupe_and_build_track_list(db, mix["tracks"])
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
) -> GenreMixItemResponse:
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
    tracks_out = await dedupe_and_build_track_list(db, mix["tracks"])
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
) -> GenreMixItemResponse:
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
    tracks_out = await dedupe_and_build_track_list(db, saved["tracks"])
    return GenreMixItemResponse(
        genre=saved["genre"],
        title=saved["title"],
        tracks=tracks_out,
    )


@router.get("/radio", response_model=RadioQueueResponse)
async def get_radio(
    seed_track_id: int = Query(...),
    queue_size: int = Query(default=20, le=50),
    exclude_ids: str = Query(default=""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RadioQueueResponse:
    exclude: list[int] = []
    if exclude_ids:
        try:
            exclude = [int(x) for x in exclude_ids.split(",") if x.strip()][
                :200
            ]
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
) -> DailyPlaylistResponse:
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
) -> WeeklyPlaylistResponse:
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
    limit: int = Query(default=100, ge=1, le=200),
) -> UserChoicePlaylistResponse:
    svc = RecommendationService(db)
    tracks = await svc.get_user_choice_playlist(limit=limit)
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
) -> WeeklyTopPlaylistResponse:
    svc = RecommendationService(db)
    payload = await svc.get_weekly_top_playlist(limit=limit)
    repo = RecommendationRepository(db)
    tracks = await repo.get_tracks_by_ids(payload.get("track_ids", []))
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
) -> ForgottenTreasuresPlaylistResponse:
    svc = RecommendationService(db)
    payload = await svc.get_forgotten_treasures_playlist(
        user.id,
        limit=limit,
    )
    repo = RecommendationRepository(db)
    tracks = await repo.get_tracks_by_ids(payload["track_ids"])
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
) -> None:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only",
        )
    svc = RecommendationService(db)
    await svc.refresh_daily_playlist(user.id)


@router.post(
    "/daily-mix/refresh",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("3/minute")
async def refresh_daily_mix(
    request: Request,
    user: User = Depends(get_current_user),
) -> None:
    redis = get_redis_client()
    await redis.delete(f"rec:daily_mix:{user.id}")


@router.post(
    "/genre-mixes/refresh",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("3/minute")
async def refresh_genre_mixes(
    request: Request,
    user: User = Depends(get_current_user),
) -> None:
    redis = get_redis_client()
    await redis.delete(f"rec:genre_mixes:{user.id}")


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
    rec_repo = RecommendationRepository(db)
    artist_repo = ArtistRepository(db)

    trending_raw = await rec_repo.get_popular_tracks(limit=trending_limit)
    trending_out = await dedupe_and_build_track_list(db, trending_raw)

    artists_raw = await artist_repo.list_popular(limit=artist_limit)
    listeners_map: dict[int, int] = {}
    if artists_raw:
        stats_repo = ArtistStatsRepository(db)
        listeners_map = await stats_repo.get_latest_listeners_batch(
            [a.id for a in artists_raw]
        )
    artists_out = [
        ArtistResponse.model_validate(
            a,
            update={"monthly_listeners": listeners_map.get(a.id, 0)},
        )
        for a in artists_raw
    ]

    genre_cards = [
        DiscoverGenreCard(
            genre=g,
            title=g,
            track_count=cnt,
            cover_key=cover,
        )
        for g, cnt, cover in await rec_repo.get_genre_cards(limit=12)
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
