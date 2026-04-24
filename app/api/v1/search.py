from __future__ import annotations

import structlog
from fastapi import (
    APIRouter,
    Query,
    Request,
    status,
)
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.observability import elasticsearch_query_observed
from app.core.rate_limit import limiter
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


@router.get(
    "/suggest",
    response_model=SuggestListResponse,
    summary="Autocomplete: tracks and artists in the local catalog",
)
@limiter.limit("60/minute")
async def search_suggest(
    request: Request,
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
    return SuggestListResponse(
        items=[
            SuggestItemResponse(
                kind=x.kind,
                id=x.id,
                title=x.title,
                name=x.name,
            )
            for x in res
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
