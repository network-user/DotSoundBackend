from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.signal import (
    ListenEventRequest,
    SearchClickRequest,
)
from app.services.signal_service import (
    SignalService,
)

router = APIRouter(
    prefix="/signals", tags=["signals"]
)


@router.post("/listen")
async def record_listen(
    body: ListenEventRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = SignalService(db)
    await svc.record_listen(
        user_id=user.id,
        track_id=body.track_id,
        duration_listened=body.duration_listened,
        total_duration=body.total_duration,
        source_context=body.source_context,
    )
    return {"status": "ok"}


@router.post("/search")
async def record_search(
    body: SearchClickRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = SignalService(db)
    await svc.record_search_click(
        user_id=user.id,
        query=body.query,
        results_count=body.results_count,
        clicked_track_id=body.clicked_track_id,
    )
    return {"status": "ok"}
