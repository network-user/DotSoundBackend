from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthError, decode_access_token
from app.core.db import AsyncSessionLocal
from app.core.ws_manager import ACTIVITY_TYPES, ws_manager
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.chat import ChatRepository
from app.repositories.user import UserRepository

router = APIRouter(tags=["websocket"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = None,
) -> None:
    if not token:
        await websocket.close(code=4001)
        return

    try:
        payload = decode_access_token(token)
    except AuthError:
        await websocket.close(code=4001)
        return

    user_id = int(str(payload["sub"]))

    async with AsyncSessionLocal() as s:
        user_repo = UserRepository(s)
        user = await user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            await websocket.close(code=4001)
            return

    await ws_manager.connect(user_id, websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event = data.get("event")
            conv_id = data.get("conversation_id")
            logger.debug(
                "ws_incoming",
                user_id=user_id,
                ws_event=event,
                conv_id=conv_id,
            )

            if not conv_id:
                continue

            if event == "activity":
                activity = data.get(
                    "activity", "typing"
                )
                if activity not in ACTIVITY_TYPES:
                    continue
                async with AsyncSessionLocal() as s:
                    repo = ChatRepository(s)
                    member_ids = (
                        await repo.get_member_ids(
                            conv_id
                        )
                    )
                members = [
                    uid
                    for uid in member_ids
                    if uid != user_id
                ]
                logger.info(
                    "ws_activity_broadcast",
                    user_id=user_id,
                    conv_id=conv_id,
                    activity=activity,
                    targets=members,
                )
                await ws_manager.broadcast_activity(
                    user_id,
                    conv_id,
                    members,
                    activity,
                )
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception(
            "ws_error", user_id=user_id
        )
    finally:
        await ws_manager.disconnect(
            user_id, websocket
        )


@router.get("/users/{target_id}/presence")
async def get_user_presence(
    target_id: int,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    data = await ws_manager.get_presence(
        target_id
    )
    return {
        "user_id": target_id,
        "status": data.get("status", "offline"),
        "last_seen": data.get("ts", 0),
    }


@router.get("/chats/{conv_id}/presence")
async def get_chat_presence(
    conv_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repo = ChatRepository(session)
    member_ids = await repo.get_member_ids(
        conv_id
    )
    presence = await ws_manager.get_presence_bulk(
        [
            uid
            for uid in member_ids
            if uid != user.id
        ]
    )
    return {
        "conversation_id": conv_id,
        "members": {
            str(uid): {
                "status": p.get(
                    "status", "offline"
                ),
                "last_seen": p.get("ts", 0),
            }
            for uid, p in presence.items()
        },
    }
