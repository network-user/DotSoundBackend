from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.core.auth import AuthError, decode_access_token
from app.core.db import AsyncSessionLocal
from app.core.ws_manager import ws_manager
from app.core.ws_origin import reject_if_bad_origin
from app.dependencies import get_current_user
from app.models.user import User
from app.repositories.user import UserRepository

# [REGULATORY-DISABLED v1] чат-обмен отключён (ст. 10.1 149-ФЗ).
# Полностью убраны импорты `AsyncSession`, `ACTIVITY_TYPES`,
# `get_db`, `ChatRepository` — они нужны только закомментированным
# ниже chat-handler'ам и chat-presence-роуту.

router = APIRouter(tags=["websocket"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = None,
) -> None:
    if await reject_if_bad_origin(websocket):
        return
    raw_token = token or ""
    proto = websocket.headers.get("sec-websocket-protocol")
    if not raw_token and proto:
        raw_token = proto.split(",")[0].strip()
    if not raw_token:
        await websocket.close(code=4001)
        return

    try:
        payload = decode_access_token(raw_token)
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

    subprotocol = proto.split(",")[0].strip() if proto else None
    if not await ws_manager.connect(
        user_id, websocket, subprotocol=subprotocol
    ):
        return

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event = data.get("event")
            logger.debug(
                "ws_incoming",
                user_id=user_id,
                ws_event=event,
            )
            # [REGULATORY-DISABLED v1] chat activity (typing) и
            # conversation-broadcast отключены вместе с чатами.
            # Принятые сообщения просто игнорируются.
            continue
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


# [REGULATORY-DISABLED v1] chat presence-роут отключён вместе с
# чатами. Восстановить вместе с `app/api/v1/chats.py`.
# @router.get("/chats/{conv_id}/presence")
# async def get_chat_presence(
#     conv_id: int,
#     user: User = Depends(get_current_user),
#     session: AsyncSession = Depends(get_db),
# ) -> dict[str, Any]:
#     repo = ChatRepository(session)
#     member_ids = await repo.get_member_ids(conv_id)
#     presence = await ws_manager.get_presence_bulk(
#         [uid for uid in member_ids if uid != user.id]
#     )
#     return {
#         "conversation_id": conv_id,
#         "members": {
#             str(uid): {
#                 "status": p.get("status", "offline"),
#                 "last_seen": p.get("ts", 0),
#             }
#             for uid, p in presence.items()
#         },
#     }
