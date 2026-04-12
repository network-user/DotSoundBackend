from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.chat import (
    AddMemberRequest,
    CreateDMRequest,
    CreateGroupRequest,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("")
async def create_chat(
    body: CreateDMRequest | CreateGroupRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ChatService(session)
    if isinstance(body, CreateGroupRequest):
        return await svc.create_group(
            user.id, body.title, body.member_ids
        )
    return await svc.create_dm(
        user.id, body.target_user_id
    )


@router.get("")
async def list_chats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    svc = ChatService(session)
    return await svc.list_chats(user.id)


@router.post("/{conv_id}/pin")
async def pin_chat(
    conv_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = ChatService(session)
    await svc.pin_chat(user.id, conv_id)
    return {"status": "pinned"}


@router.delete("/{conv_id}/pin")
async def unpin_chat(
    conv_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = ChatService(session)
    await svc.unpin_chat(user.id, conv_id)
    return {"status": "unpinned"}


@router.post("/{conv_id}/members")
async def add_member(
    conv_id: int,
    body: AddMemberRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = ChatService(session)
    await svc.add_member(
        user.id, conv_id, body.user_id
    )
    return {"status": "added"}


@router.delete("/{conv_id}/members/{target_id}")
async def remove_member(
    conv_id: int,
    target_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = ChatService(session)
    await svc.remove_member(
        user.id, conv_id, target_id
    )
    return {"status": "removed"}
