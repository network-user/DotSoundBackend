"""Lyrics endpoints — CRUD + synced timecodes + progress stream."""

import asyncio
import json

import structlog
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rate_limit import limiter
from app.core.redis import get_redis_client
from app.dependencies import (
    get_current_user,
    get_db,
    get_optional_user,
)
from app.models.user import User
from app.schemas.lyrics import (
    LyricsAutoRequest,
    LyricsAutoResponse,
    LyricsAutoStatusResponse,
    LyricsCreateRequest,
    LyricsResponse,
    LyricsTranslationResponse,
    LyricsTranslationUpsertRequest,
    LyricsSyncRequest,
)
from app.services.lyrics_service import LyricsService
from app.services.lyrics_worker import (
    EVENTS_CHANNEL_PREFIX,
    TERMINAL_STATES,
    get_lyrics_progress,
)

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
        track_id=track_id,
        user_id=current_user.id,
        plain_text=body.plain_text,
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
    current_user: User | None = Depends(get_optional_user),
) -> LyricsResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = LyricsService(session)
    lyrics = await service.get_lyrics(
        track_id,
        requester_id=current_user.id if current_user else None,
    )
    if not lyrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lyrics not found",
        )
    return LyricsResponse.model_validate(lyrics)


@router.put(
    "/{track_id}/lyrics/sync",
    response_model=LyricsResponse,
    summary=(
        "Update synced timecodes (owner only). Requires "
        "existing plain-text lyrics."
    ),
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
    synced_dicts = [
        line.model_dump() for line in body.synced_lines
    ]
    lyrics = await service.update_sync(
        track_id=track_id,
        user_id=current_user.id,
        synced_lines=synced_dicts,
    )
    return LyricsResponse.model_validate(lyrics)


@router.get(
    "/{track_id}/lyrics/translations",
    response_model=list[LyricsTranslationResponse],
    summary="List lyrics translations for a track",
)
@limiter.limit("200/minute")
async def list_lyrics_translations(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> list[LyricsTranslationResponse]:
    service = LyricsService(session)
    items = await service.list_translations(
        track_id=track_id,
        requester_id=current_user.id if current_user else None,
    )
    return [
        LyricsTranslationResponse.model_validate(item)
        for item in items
    ]


@router.put(
    "/{track_id}/lyrics/translations/{language_code}",
    response_model=LyricsTranslationResponse,
    summary="Create or update lyrics translation (owner only)",
)
@limiter.limit("30/minute")
async def upsert_lyrics_translation(
    request: Request,
    track_id: int,
    language_code: str,
    body: LyricsTranslationUpsertRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LyricsTranslationResponse:
    service = LyricsService(session)
    item = await service.upsert_translation(
        track_id=track_id,
        user_id=current_user.id,
        language_code=language_code,
        translated_text=body.translated_text,
    )
    return LyricsTranslationResponse.model_validate(item)


@router.delete(
    "/{track_id}/lyrics/translations/{language_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete lyrics translation (owner only)",
)
@limiter.limit("30/minute")
async def delete_lyrics_translation(
    request: Request,
    track_id: int,
    language_code: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    service = LyricsService(session)
    removed = await service.delete_translation(
        track_id=track_id,
        user_id=current_user.id,
        language_code=language_code,
    )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lyrics translation not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
) -> Response:
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
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    body: LyricsAutoRequest = Body(default_factory=LyricsAutoRequest),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LyricsAutoResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    logger.info(
        "lyrics_auto_requested",
        track_id=track_id,
        with_sync=body.with_sync,
        bypass_cache=body.bypass_cache,
    )
    bypass_cache = body.bypass_cache
    if bypass_cache and not (
        current_user.is_admin or settings.debug
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="bypass_cache requires admin",
        )
    service = LyricsService(session)
    task_id = await service.trigger_auto_generation(
        track_id=track_id,
        user_id=current_user.id,
        with_sync=body.with_sync,
        bypass_cache=bypass_cache,
    )
    return LyricsAutoResponse(task_id=task_id)


def _validate_task_id(task_id: str) -> bool:
    return bool(task_id) and len(task_id) <= 128


def _status_from_progress(
    progress: dict | None,
) -> LyricsAutoStatusResponse:
    if not progress:
        return LyricsAutoStatusResponse(status="pending")

    stage = progress.get("stage")
    logs = progress.get("logs", []) or []
    percent = progress.get("percent")
    terminal = progress.get("terminal_state")

    if terminal in TERMINAL_STATES:
        return LyricsAutoStatusResponse(
            status=terminal,
            stage=stage,
            percent=percent,
            logs=logs,
        )

    return LyricsAutoStatusResponse(
        status="pending",
        stage=stage,
        percent=percent,
        logs=logs,
    )


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
    if not _validate_task_id(task_id):
        return LyricsAutoStatusResponse(status="error")

    try:
        progress = await get_lyrics_progress(task_id)
    except Exception:
        logger.exception(
            "lyrics_progress_fetch_error", task_id=task_id
        )
        return LyricsAutoStatusResponse(status="pending")

    return _status_from_progress(progress)


def _sse_event(name: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {name}\ndata: {payload}\n\n"


@router.get(
    "/{track_id}/lyrics/auto/events",
    summary=(
        "Server-Sent Events stream for auto-detection progress"
    ),
)
async def stream_auto_lyrics_events(
    request: Request,
    track_id: int,
    task_id: str,
) -> StreamingResponse:
    if not _validate_task_id(task_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task_id",
        )

    channel = f"{EVENTS_CHANNEL_PREFIX}{task_id}"

    async def event_generator():
        redis = get_redis_client()
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)

        try:
            snapshot = await get_lyrics_progress(task_id)
            resp = _status_from_progress(snapshot)
            yield _sse_event(
                "snapshot", resp.model_dump()
            )

            if resp.status in TERMINAL_STATES:
                return

            idle_retries = 0
            while True:
                if await request.is_disconnected():
                    break
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=15.0,
                )
                if msg is None:
                    idle_retries += 1
                    yield ": keep-alive\n\n"
                    if idle_retries > 40:
                        break
                    continue
                idle_retries = 0
                data_raw = msg.get("data")
                if not data_raw:
                    continue
                try:
                    data = (
                        json.loads(data_raw)
                        if isinstance(data_raw, str)
                        else json.loads(
                            data_raw.decode("utf-8")
                        )
                    )
                except (TypeError, ValueError):
                    continue
                yield _sse_event(
                    data.get("type", "progress"), data
                )
                if data.get("terminal_state") in TERMINAL_STATES:
                    break
        except asyncio.CancelledError:
            raise
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except Exception:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post(
    "/{track_id}/lyrics/redefine",
    response_model=LyricsAutoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete existing lyrics and re-run auto-detection",
)
@limiter.limit("10/minute")
async def redefine_lyrics(
    request: Request,
    track_id: int,
    body: LyricsAutoRequest = Body(default_factory=LyricsAutoRequest),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LyricsAutoResponse:
    """Delete existing lyrics for a track and re-run detection.

    The (artist, title) result cache is always invalidated here
    so a real re-detection happens, not a silent re-load of the
    previously cached provider answer.

    ``bypass_cache`` additionally tells the worker to skip cache
    reads on this run. Gated to admin users (or debug builds) so
    regular owners can't bypass cost-saving behaviour.
    """
    bypass_cache = body.bypass_cache
    if bypass_cache and not (
        current_user.is_admin or settings.debug
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="bypass_cache requires admin",
        )

    structlog.contextvars.bind_contextvars(
        track_id=track_id,
        bypass_cache=bypass_cache,
    )
    service = LyricsService(session)
    progress_id = await service.redefine_lyrics(
        track_id=track_id,
        user_id=current_user.id,
        with_sync=body.with_sync,
        bypass_cache=bypass_cache,
    )
    logger.info(
        "lyrics_redefine_requested",
        progress_id=progress_id,
        with_sync=body.with_sync,
        bypass_cache=bypass_cache,
        admin=current_user.is_admin,
    )
    return LyricsAutoResponse(task_id=progress_id)


@router.post(
    "/{track_id}/lyrics/auto/cancel",
    summary="Cancel running lyrics detection task",
)
@limiter.limit("30/minute")
async def cancel_lyrics_generation(
    request: Request,
    track_id: int,
    task_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not _validate_task_id(task_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task_id",
        )

    structlog.contextvars.bind_contextvars(
        track_id=track_id, task_id=task_id
    )
    service = LyricsService(session)
    await service.cancel_auto_generation(
        track_id=track_id,
        user_id=current_user.id,
        progress_id=task_id,
    )

    return {"status": "cancel_requested"}


@router.post(
    "/{track_id}/lyrics/debug/stage/{stage_id}",
    response_model=LyricsAutoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="[DEBUG] Test individual lyrics detection stage",
)
@limiter.limit("20/minute")
async def trigger_debug_lyrics(
    request: Request,
    track_id: int,
    stage_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LyricsAutoResponse:
    if not settings.debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug mode not enabled",
        )

    if stage_id not in (1, 2, 3):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid stage_id",
        )

    structlog.contextvars.bind_contextvars(
        track_id=track_id, debug_stage_id=stage_id
    )

    service = LyricsService(session)
    await service._get_owned_track(
        track_id=track_id, user_id=current_user.id
    )

    import uuid

    from app.services.lyrics_worker import (
        generate_lyrics_debug_task,
        set_lyrics_progress,
    )

    progress_id = uuid.uuid4().hex
    task = await generate_lyrics_debug_task.kiq(
        track_id=track_id,
        stage_id=stage_id,
        progress_id=progress_id,
    )
    await set_lyrics_progress(
        progress_id,
        stage="queued",
        log_line=f"debug task queued: taskiq_id={task.task_id}",
        percent=2,
    )

    logger.info(
        "debug_lyrics_triggered",
        stage_id=stage_id,
        task_id=task.task_id,
        progress_id=progress_id,
    )

    return LyricsAutoResponse(task_id=progress_id)
