from __future__ import annotations

import structlog
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Request,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import s3
from app.core.observability import elasticsearch_query_observed
from app.core.rate_limit import limiter
from app.dependencies import get_db
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.search_author import (
    PlatformAuthorSearchItem,
    PlatformAuthorSearchListResponse,
)
from app.schemas.search_suggest import (
    SuggestItemResponse,
    SuggestListResponse,
)
from app.search.es_client import es_available
from app.services import search_query_service
from app.services.search_index_service import (
    reindex_all_tracks_artist_backfill,
)

router = APIRouter(prefix="/search", tags=["search"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _platform_author_display_name(user: User) -> str:
    if user.display_name and user.display_name.strip():
        return user.display_name.strip()
    parts = [user.first_name]
    if user.last_name and user.last_name.strip():
        parts.append(user.last_name.strip())
    joined = " ".join(parts).strip()
    return joined or "—"


async def _platform_author_avatar_url(user: User) -> str:
    if user.avatar_key:
        return await s3.get_presigned_url(user.avatar_key)
    seed = user.avatar_seed or (
        str(user.telegram_id)
        if user.telegram_id is not None
        else str(user.id)
    )
    return f"https://api.dicebear.com/9.x/identicon/svg?seed={seed}"


@router.get(
    "/authors",
    response_model=PlatformAuthorSearchListResponse,
    summary="Search platform users who have public uploads (for catalog search)",
)
@limiter.limit("60/minute")
async def search_platform_authors(
    request: Request,
    db: AsyncSession = Depends(get_db),
    q: str = Query(
        min_length=1,
        max_length=200,
        description="Match against username, names, display_name",
    ),
    limit: int = Query(10, ge=1, le=20),
) -> PlatformAuthorSearchListResponse:
    repo = UserRepository(db)
    users = await repo.search_platform_authors(q.strip(), limit=limit)
    items: list[PlatformAuthorSearchItem] = []
    for u in users:
        avatar_url = await _platform_author_avatar_url(u)
        items.append(
            PlatformAuthorSearchItem(
                id=int(u.id),
                display_name=_platform_author_display_name(u),
                username=u.username,
                avatar_url=avatar_url,
            )
        )
    return PlatformAuthorSearchListResponse(items=items)


@router.get(
    "/suggest",
    response_model=SuggestListResponse,
    summary="Autocomplete: tracks and artists in the local catalog",
)
@limiter.limit("60/minute")
async def search_suggest(
    request: Request,
    db: AsyncSession = Depends(get_db),
    q: str = Query(
        min_length=1, max_length=200, description="User input prefix"
    ),
    limit: int = Query(8, ge=1, le=25),
) -> SuggestListResponse:
    if (
        not (settings.elasticsearch_enabled)
        or not (settings.elasticsearch_url or "").strip()
    ):
        return SuggestListResponse(items=[])
    if not es_available():
        return SuggestListResponse(items=[])
    try:
        res = await search_query_service.es_suggest_mixed(q, limit=limit)
    except Exception:  # noqa: BLE001
        logger.exception("suggest_unhandled")
        elasticsearch_query_observed(op="suggest", outcome="es_error")
        return SuggestListResponse(items=[])
    if res is None:
        elasticsearch_query_observed(op="suggest", outcome="es_fail")
        return SuggestListResponse(items=[])
    elasticsearch_query_observed(op="suggest", outcome="es_ok")
    enriched = await search_query_service.enrich_suggest_tracks_from_db(
        db, res
    )
    return SuggestListResponse(
        items=[
            SuggestItemResponse(
                kind=x.kind,
                id=x.id,
                title=x.title,
                name=x.name,
                cover_key=x.cover_key,
                duration_seconds=x.duration_seconds,
            )
            for x in enriched
        ]
    )


@router.get(
    "/_admin/reindex",
    include_in_schema=False,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("2/minute")
async def _admin_reindex(
    request: Request,
) -> JSONResponse:
    if not settings.debug:
        return JSONResponse(status_code=404, content={})
    if not es_available():
        return JSONResponse(
            {
                "ok": False,
                "reason": "es_unavailable",
            }
        )
    n = await reindex_all_tracks_artist_backfill()
    return JSONResponse(
        {
            "ok": True,
            "tracks": n,
        }
    )
