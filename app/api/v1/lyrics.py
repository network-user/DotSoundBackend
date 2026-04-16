"""Lyrics endpoints — CRUD + synced timecodes for tracks."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.lyrics import (
    LyricsAutoRequest,
    LyricsAutoResponse,
    LyricsAutoStatusResponse,
    LyricsCreateRequest,
    LyricsResponse,
    LyricsSyncRequest,
)
from app.services.lyrics_service import LyricsService

router = APIRouter(prefix="/tracks", tags=["lyrics"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.post(
    "/{track_id}/lyrics",
    response_model=LyricsResponse,
    summary="Create or update plain-text lyrics (owner only)",
)
@limiter.limit("30/minute")
async def upsert_lyrics(
    request: Request,
    track_id: int,
    body: LyricsCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LyricsResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = LyricsService(session)
    lyrics = await service.create_or_update(
        track_id=track_id, user_id=current_user.id, plain_text=body.plain_text
    )
    return LyricsResponse.model_validate(lyrics)


@router.get(
    "/{track_id}/lyrics",
    response_model=LyricsResponse,
    summary="Get lyrics for a track",
)
@limiter.limit("200/minute")
async def get_lyrics(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
) -> LyricsResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = LyricsService(session)
    lyrics = await service.get_lyrics(track_id)
    if not lyrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lyrics not found",
        )
    return LyricsResponse.model_validate(lyrics)


@router.put(
    "/{track_id}/lyrics/sync",
    response_model=LyricsResponse,
    summary="Update synced timecodes (owner only). Requires existing plain-text lyrics.",
)
@limiter.limit("30/minute")
async def update_sync(
    request: Request,
    track_id: int,
    body: LyricsSyncRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LyricsResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = LyricsService(session)
    synced_dicts = [line.model_dump() for line in body.synced_lines]
    lyrics = await service.update_sync(
        track_id=track_id, user_id=current_user.id, synced_lines=synced_dicts
    )
    return LyricsResponse.model_validate(lyrics)


@router.delete(
    "/{track_id}/lyrics",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete lyrics for a track (owner only)",
)
@limiter.limit("30/minute")
async def delete_lyrics(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = LyricsService(session)
    removed = await service.delete_lyrics(
        track_id=track_id, user_id=current_user.id
    )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lyrics not found",
        )


@router.post(
    "/{track_id}/lyrics/auto",
    response_model=LyricsAutoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger auto-detection of lyrics (owner only)",
)
@limiter.limit("10/minute")
async def trigger_auto_lyrics(
    request: Request,
    track_id: int,
    body: LyricsAutoRequest = LyricsAutoRequest(),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LyricsAutoResponse:
    structlog.contextvars.bind_contextvars(
        track_id=track_id
    )
    service = LyricsService(session)
    task_id = await service.trigger_auto_generation(
        track_id=track_id,
        user_id=current_user.id,
        with_sync=body.with_sync,
    )
    return LyricsAutoResponse(task_id=task_id)


@router.get(
    "/{track_id}/lyrics/auto/status",
    response_model=LyricsAutoStatusResponse,
    summary="Poll auto-detection task status",
)
@limiter.limit("60/minute")
async def get_auto_lyrics_status(
    request: Request,
    track_id: int,
    task_id: str,
) -> LyricsAutoStatusResponse:
    from app.services.lyrics_worker import (
        get_lyrics_progress,
    )

    if not task_id or len(task_id) > 128:
        return LyricsAutoStatusResponse(
            status="error"
        )

    progress = await get_lyrics_progress(task_id)
    stage = progress.get("stage") if progress else None
    logs = progress.get("logs", []) if progress else []

    status_from_stage: dict[str, str] = {
        "error": "error",
    }
    final_status = status_from_stage.get(
        stage or "", ""
    )
    if final_status:
        return LyricsAutoStatusResponse(
            status=final_status,
            stage=stage,
            logs=logs,
        )

    has_done_log = any(
        "saved to DB" in line for line in logs
    )
    has_not_found_log = any(
        "lyrics not found" in line for line in logs
    )
    has_error_log = any(
        "ERROR:" in line for line in logs
    )

    if has_done_log:
        return LyricsAutoStatusResponse(
            status="found",
            stage=stage,
            logs=logs,
        )
    if has_not_found_log:
        return LyricsAutoStatusResponse(
            status="not_found",
            stage=stage,
            logs=logs,
        )
    if has_error_log:
        return LyricsAutoStatusResponse(
            status="error",
            stage=stage,
            logs=logs,
        )

    return LyricsAutoStatusResponse(
        status="pending",
        stage=stage,
        logs=logs,
    )


# ========== DEBUG ENDPOINTS (only available when DEBUG=true) ==========


@router.post(
    "/{track_id}/lyrics/debug/tier/{tier_num}",
    response_model=LyricsAutoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="[DEBUG] Test individual lyrics detection tier (1, 2, or 3)",
)
@limiter.limit("20/minute")
async def trigger_debug_lyrics(
    request: Request,
    track_id: int,
    tier_num: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LyricsAutoResponse:
    if not settings.debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug mode not enabled",
        )

    if tier_num not in (1, 2, 3):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tier must be 1, 2, or 3",
        )

    structlog.contextvars.bind_contextvars(
        track_id=track_id, debug_tier=tier_num
    )

    service = LyricsService(session)
    await service._get_owned_track(
        track_id=track_id, user_id=current_user.id
    )

    from app.services.lyrics_worker import (
        generate_lyrics_debug_task,
        set_lyrics_progress,
    )
    import uuid

    progress_id = uuid.uuid4().hex
    task = await generate_lyrics_debug_task.kiq(
        track_id=track_id, tier=tier_num, progress_id=progress_id
    )
    await set_lyrics_progress(
        progress_id,
        "queued",
        f"debug task queued (tier={tier_num}): taskiq_id={task.task_id}",
    )

    logger.info(
        "debug_lyrics_triggered",
        tier=tier_num,
        task_id=task.task_id,
        progress_id=progress_id,
    )

    return LyricsAutoResponse(task_id=progress_id)
