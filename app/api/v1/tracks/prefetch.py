"""Stream URL prefetch endpoint — warms cache for upcoming tracks."""

import asyncio

import structlog
from fastapi import APIRouter, Body, Depends, Request, status
from pydantic import BaseModel, Field

from app.config import settings
from app.core.observability import offline_prefetch_observed
from app.core.rate_limit import limiter
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _log_prefetch_done(task: asyncio.Task[None]) -> None:
    exc = task.exception()
    if exc is not None:
        offline_prefetch_observed(outcome="error")
        logger.warning(
            "prefetch_track_urls_failed",
            err=str(exc),
        )
    else:
        offline_prefetch_observed(outcome="completed")


_MAX_BODY_TRACK_IDS = 2000


def _effective_prefetch_cap() -> int:
    raw = settings.audio_cache_prefetch_max_ids
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = 20
    return max(1, min(n, _MAX_BODY_TRACK_IDS))


class PrefetchRequest(BaseModel):
    track_ids: list[int] = Field(
        ...,
        max_length=_MAX_BODY_TRACK_IDS,
    )


class PrefetchResponse(BaseModel):
    accepted: int


@router.post(
    "/prefetch",
    response_model=PrefetchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Warm stream URL cache for upcoming tracks (fire-and-forget)",
)
@limiter.limit("30/minute")
async def prefetch_tracks(
    request: Request,
    payload: PrefetchRequest = Body(...),
    current_user: User = Depends(get_current_user),
) -> PrefetchResponse:
    from app.services.audio_cache_prefetch import prefetch_track_urls

    cap = _effective_prefetch_cap()
    ids = payload.track_ids[:cap]
    if not ids:
        offline_prefetch_observed(outcome="accepted")
        return PrefetchResponse(accepted=0)
    task = asyncio.create_task(prefetch_track_urls(ids))
    task.add_done_callback(_log_prefetch_done)
    offline_prefetch_observed(outcome="accepted")
    return PrefetchResponse(accepted=len(ids))
