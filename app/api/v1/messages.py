from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.s3 import (
    upload_image,
    upload_voice,
)
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.message import (
    MessageRepository,
)
from app.schemas.chat import (
    MarkReadRequest,
    ReactionRequest,
    SendMessageRequest,
)
from app.services.message_service import (
    MessageService,
)

router = APIRouter(tags=["messages"])


@router.get("/chats/{conv_id}/messages")
async def get_messages(
    conv_id: int,
    cursor: int | None = None,
    limit: int = 20,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    svc = MessageService(session)
    return await svc.get_messages(
        conv_id,
        user.id,
        cursor,
        min(limit, 50),
    )


@router.post("/chats/{conv_id}/messages")
async def send_message(
    conv_id: int,
    body: SendMessageRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = MessageService(session)
    return await svc.send_message(
        conv_id,
        user.id,
        body.content,
        body.type,
        body.reply_to_id,
        body.shared_track_id,
    )


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = MessageService(session)
    await svc.delete_message(message_id, user.id)
    return {"status": "deleted"}


@router.post("/messages/{message_id}/reactions")
async def add_reaction(
    message_id: int,
    body: ReactionRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = MessageService(session)
    await svc.add_reaction(
        message_id, user.id, body.reaction_type
    )
    return {"status": "added"}


@router.delete(
    "/messages/{message_id}/reactions/{rtype}"
)
async def remove_reaction(
    message_id: int,
    rtype: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = MessageService(session)
    await svc.remove_reaction(
        message_id, user.id, rtype
    )
    return {"status": "removed"}


@router.post("/chats/{conv_id}/messages/read")
async def mark_read(
    conv_id: int,
    body: MarkReadRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = MessageService(session)
    await svc.mark_as_read(
        conv_id, user.id, body.message_id
    )
    return {"status": "read"}


@router.post("/chats/{conv_id}/messages/photo")
async def upload_photo(
    conv_id: int,
    file: UploadFile,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    data = await file.read()
    img_key, thumb_key, w, h = await upload_image(
        data, prefix="chat_photos", user_id=user.id
    )

    msg_svc = MessageService(session)
    result = await msg_svc.send_message(
        conv_id, user.id, "", "photo"
    )

    msg_repo = MessageRepository(session)
    att = await msg_repo.add_attachment(
        message_id=result["id"],
        file_key=img_key,
        file_type="photo",
        file_size_bytes=len(data),
        width=w,
        height=h,
    )
    result["attachments"] = [
        {
            "id": att.id,
            "file_key": img_key,
            "file_type": "photo",
            "width": w,
            "height": h,
        }
    ]
    return result


@router.post("/chats/{conv_id}/messages/voice")
async def upload_voice_msg(
    conv_id: int,
    file: UploadFile,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    data = await file.read()
    file_key, duration, waveform = (
        await upload_voice(data, user_id=user.id)
    )

    msg_svc = MessageService(session)
    result = await msg_svc.send_message(
        conv_id, user.id, "", "voice"
    )

    msg_repo = MessageRepository(session)
    att = await msg_repo.add_attachment(
        message_id=result["id"],
        file_key=file_key,
        file_type="voice",
        file_size_bytes=len(data),
        duration_seconds=duration,
        waveform=waveform,
    )
    result["attachments"] = [
        {
            "id": att.id,
            "file_key": file_key,
            "file_type": "voice",
            "duration_seconds": duration,
            "waveform": waveform,
        }
    ]
    return result
