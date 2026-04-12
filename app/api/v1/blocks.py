from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.services.block_service import BlockService

router = APIRouter(tags=["blocks"])


@router.post("/users/{target_id}/block")
async def block_user(
    target_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = BlockService(session)
    await svc.block_user(user.id, target_id)
    return {"status": "blocked"}


@router.delete("/users/{target_id}/block")
async def unblock_user(
    target_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = BlockService(session)
    await svc.unblock_user(user.id, target_id)
    return {"status": "unblocked"}


@router.get("/blocks")
async def list_blocks(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, list[int]]:
    svc = BlockService(session)
    blocked = await svc.get_blocked_users(user.id)
    return {"blocked_user_ids": blocked}
