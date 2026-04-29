import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.track import SCSearchResult, TrackResponse
from app.services.soundcloud_service import SoundCloudService
from app.services.track_response_build import build_track_response

router = APIRouter(prefix="/soundcloud", tags=["soundcloud"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class SCImportRequest(BaseModel):
    sc_url: str
    is_public: bool = True


def _format_result(item: dict) -> SCSearchResult:  # type: ignore[type-arg]
    user_data = item.get("user", {})
    artist = user_data.get("username") or user_data.get("full_name")
    duration_ms: int | None = item.get("duration")
    return SCSearchResult(
        sc_id=item["id"],
        title=item.get("title", "Unknown"),
        artist=artist,
        duration_seconds=duration_ms // 1000 if duration_ms else None,
        artwork_url=item.get("artwork_url"),
        sc_url=item.get("permalink_url", ""),
        sc_uri=item.get("uri", ""),
    )


@router.get(
    "/search",
    response_model=list[SCSearchResult],
    summary="Search tracks on SoundCloud",
)
@limiter.limit("30/minute")
async def search_soundcloud(
    request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
) -> list[SCSearchResult]:
    structlog.contextvars.bind_contextvars(search_query=q)
    service = SoundCloudService(settings.sc_client_id, session)
    results = await service.search(q, limit=limit)
    logger.info("sc_search_endpoint", query=q, count=len(results))
    return [_format_result(item) for item in results]


@router.post(
    "/import",
    response_model=TrackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import a SoundCloud track by URL (authenticated)",
)
@limiter.limit("20/minute")
async def import_soundcloud_track(
    request: Request,
    data: SCImportRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackResponse:
    structlog.contextvars.bind_contextvars(sc_url=data.sc_url)
    if not data.sc_url.startswith("https://soundcloud.com/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must be a soundcloud.com track link",
        )
    service = SoundCloudService(settings.sc_client_id, session)
    sc_data = await service.resolve_url(data.sc_url)
    if sc_data.get("kind") != "track":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL is not a track",
        )
    track = await service.import_or_get_track(
        sc_data=sc_data,
        uploader_id=current_user.id,
        is_public=data.is_public,
    )
    if track.artist:
        from app.services.artist_service import ArtistService

        artist_svc = ArtistService(session)
        try:
            linked = await artist_svc.resolve_and_link(
                track_id=track.id,
                raw_artist_string=track.artist,
                source="soundcloud",
            )
            if linked:
                user_payload = sc_data.get("user")
                if isinstance(user_payload, dict):
                    await service.sync_artist_soundcloud_uploader_profile(
                        linked[0].id,
                        user_payload,
                        uploader_id=current_user.id,
                    )
            await session.commit()
        except Exception:
            logger.warning(
                "sc_import_artist_link_failed",
                track_id=track.id,
            )
            await session.rollback()
    logger.info(
        "sc_import_endpoint", track_id=track.id, sc_url=data.sc_url
    )
    return await build_track_response(session, track)
