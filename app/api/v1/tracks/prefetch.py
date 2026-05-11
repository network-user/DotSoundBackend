"""Stream URL prefetch endpoint — warms cache for upcoming tracks."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.config import settings
from app.core.rate_limit import limiter
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _log_prefetch_done(task: asyncio.Task[None]) -> None:
    exc = task.exception()
    if exc is not None:
        logger.warning(
            "prefetch_track_urls_failed",
            err=str(exc),
        )


class PrefetchRequest(BaseModel):
    track_ids: list[int] = Field(
        ..., max_length=settings.audio_cache_prefetch_max_ids
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
    body: PrefetchRequest,
    current_user: User = Depends(get_current_user),
) -> PrefetchResponse:
    from app.services.audio_cache_prefetch import prefetch_track_urls

    task = asyncio.create_task(prefetch_track_urls(body.track_ids))
    task.add_done_callback(_log_prefetch_done)
    return PrefetchResponse(accepted=len(body.track_ids))
