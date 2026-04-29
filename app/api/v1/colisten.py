import contextlib
import uuid

import structlog
from fastapi import (
    APIRouter,
    Body,
    Depends,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthError, decode_access_token
from app.core.rate_limit import limiter
from app.core.redis import get_redis_client
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.colisten import (
    CoListenCreateBody,
    CoListenPatchBody,
    CoListenRoomState,
)
from app.services.co_listen_service import CoListenService

router = APIRouter(prefix="/colisten", tags=["co-listen"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

_CHANNEL_FMT = "colisten:room:{}"


@router.post(
    "/rooms",
    response_model=CoListenRoomState,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/minute")
async def create_colisten_room(
    request: Request,
    payload: CoListenCreateBody = Body(...),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CoListenRoomState:
    svc = CoListenService(session)
    r = await svc.create_room(user, payload.track_id)
    return CoListenRoomState(
        id=str(r.id),
        host_id=int(r.host_id),
        dj_id=(int(r.dj_id) if r.dj_id is not None else None),
        track_id=int(r.track_id),
        position_ms=int(r.position_ms),
        is_playing=bool(r.is_playing),
        epoch=int(r.epoch),
        expires_at=r.expires_at,
    )


@router.get(
    "/rooms/{room_id}",
    response_model=CoListenRoomState,
)
@limiter.limit("200/minute")
async def get_colisten_room(
    request: Request,
    room_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> CoListenRoomState:
    svc = CoListenService(session)
    r = await svc.get_room(room_id)
    return CoListenRoomState(
        id=str(r.id),
        host_id=int(r.host_id),
        dj_id=(int(r.dj_id) if r.dj_id is not None else None),
        track_id=int(r.track_id),
        position_ms=int(r.position_ms),
        is_playing=bool(r.is_playing),
        epoch=int(r.epoch),
        expires_at=r.expires_at,
    )


@router.patch(
    "/rooms/{room_id}",
    response_model=CoListenRoomState,
)
@limiter.limit("200/minute")
async def patch_colisten_room(
    request: Request,
    room_id: uuid.UUID,
    payload: CoListenPatchBody = Body(...),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CoListenRoomState:
    svc = CoListenService(session)
    r = await svc.patch_state(
        room_id,
        user,
        position_ms=payload.position_ms,
        is_playing=payload.is_playing,
        track_id=payload.track_id,
    )
    return CoListenRoomState(
        id=str(r.id),
        host_id=int(r.host_id),
        dj_id=(int(r.dj_id) if r.dj_id is not None else None),
        track_id=int(r.track_id),
        position_ms=int(r.position_ms),
        is_playing=bool(r.is_playing),
        epoch=int(r.epoch),
        expires_at=r.expires_at,
    )


@router.websocket("/ws/{room_id}")
async def colisten_ws(
    websocket: WebSocket,
    room_id: uuid.UUID,
    token: str | None = Query(None),
) -> None:
    if not token:
        await websocket.close(code=4401)
        return
    try:
        payload = decode_access_token(token)
    except AuthError:
        await websocket.close(code=4401)
        return
    int(str(payload["sub"]))
    await websocket.accept()
    rcli = get_redis_client()
    ch = _CHANNEL_FMT.format(str(room_id))
    pubsub = rcli.pubsub()
    try:
        await pubsub.subscribe(ch)
    except Exception as exc:
        logger.warning(
            "colisten_ws_subscribe_failed",
            err=str(exc),
        )
        await websocket.close(code=4500)
        return
    try:
        while True:
            msg = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=30.0,
            )
            if msg and msg.get("type") == "message":
                data = msg.get("data")
                if data:
                    await websocket.send_text(str(data))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("colisten_ws_error", err=str(exc))
    finally:
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(ch)
            await pubsub.aclose()
        with contextlib.suppress(Exception):
            await websocket.close()
