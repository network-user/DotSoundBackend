import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import client_playback_event_observed
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.signal import (
    BatchListenEventRequest,
    ClientPlaybackEventRequest,
    ListenEventRequest,
    SearchClickRequest,
)
from app.services.radio_auto_skip_stats_service import (
    record_radio_auto_skip_reason,
)
from app.services.signal_service import (
    SignalService,
)

router = APIRouter(
    prefix="/signals", tags=["signals"]
)
logger = structlog.get_logger(__name__)


@router.post("/listen/batch")
async def record_listen_batch(
    body: BatchListenEventRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = SignalService(db)
    for event in body.events:
        await svc.record_listen(
            user_id=user.id,
            track_id=event.track_id,
            duration_listened=event.duration_listened,
            total_duration=event.total_duration,
            source_context=event.source_context,
            last_position=event.last_position,
        )
    return {"status": "ok", "processed": len(body.events)}


@router.post("/listen")
async def record_listen(
    body: ListenEventRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = SignalService(db)
    await svc.record_listen(
        user_id=user.id,
        track_id=body.track_id,
        duration_listened=body.duration_listened,
        total_duration=body.total_duration,
        source_context=body.source_context,
        last_position=body.last_position,
    )
    return {"status": "ok"}


@router.post("/search")
async def record_search(
    body: SearchClickRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = SignalService(db)
    await svc.record_search_click(
        user_id=user.id,
        query=body.query,
        results_count=body.results_count,
        clicked_track_id=body.clicked_track_id,
    )
    return {"status": "ok"}


@router.post("/client/playback-event")
async def record_client_playback_event(
    body: ClientPlaybackEventRequest,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    client_playback_event_observed(
        event_name=body.event_name,
        surface=body.surface,
    )
    await record_radio_auto_skip_reason(
        error_code=body.error_code,
        error_reason=body.error_reason,
    )
    logger.info(
        "client_playback_event",
        event_name=body.event_name,
        surface=body.surface,
        user_id=user.id,
        current_track_id=body.current_track_id,
        radio_seed_track_id=body.radio_seed_track_id,
        consecutive_skips=body.consecutive_skips,
        queue_size=body.queue_size,
        error_code=body.error_code,
        error_reason=body.error_reason,
    )
    return {"status": "ok"}
