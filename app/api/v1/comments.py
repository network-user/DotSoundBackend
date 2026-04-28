from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.chat import CommentRequest, VoteRequest
from app.services.comment_service import (
    CommentService,
)

router = APIRouter(tags=["comments"])


@router.post("/tracks/{track_id}/comments")
async def add_comment(
    track_id: int,
    body: CommentRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = CommentService(session)
    return await svc.add_comment(
        track_id,
        user.id,
        body.text,
        body.parent_id,
    )


@router.get("/tracks/{track_id}/comments")
async def get_comments(
    track_id: int,
    cursor: int | None = None,
    limit: int = 20,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    svc = CommentService(session)
    return await svc.get_comments(
        track_id,
        user.id,
        cursor,
        min(limit, 50),
    )


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = CommentService(session)
    await svc.delete_comment(comment_id, user.id)
    return {"status": "deleted"}


@router.post("/comments/{comment_id}/pin")
async def pin_comment(
    comment_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = CommentService(session)
    await svc.pin_comment(comment_id, user.id)
    return {"status": "pinned"}


@router.delete("/comments/{comment_id}/pin")
async def unpin_comment(
    comment_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = CommentService(session)
    await svc.unpin_comment(comment_id, user.id)
    return {"status": "unpinned"}


@router.post("/comments/{comment_id}/hide")
async def hide_comment(
    comment_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = CommentService(session)
    await svc.hide_for_all(comment_id, user.id)
    return {"status": "hidden"}


@router.post("/comments/{comment_id}/hide-for-me")
async def hide_comment_for_me(
    comment_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = CommentService(session)
    await svc.hide_for_self(comment_id, user.id)
    return {"status": "hidden"}


@router.post("/comments/{comment_id}/vote")
async def vote_comment(
    comment_id: int,
    body: VoteRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = CommentService(session)
    await svc.vote(
        comment_id, user.id, body.is_like
    )
    return {"status": "voted"}


@router.delete("/comments/{comment_id}/vote")
async def remove_vote(
    comment_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = CommentService(session)
    await svc.remove_vote(comment_id, user.id)
    return {"status": "removed"}
