from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.chat import (
    ReadNotificationsRequest,
    UnreadNotificationRequest,
)
from app.services.notification_service import (
    NotificationService,
)

router = APIRouter(
    prefix="/notifications", tags=["notifications"]
)


@router.get("")
async def list_notifications(
    cursor: int | None = None,
    limit: int = 20,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    svc = NotificationService(session)
    return await svc.list_notifications(
        user.id, cursor, min(limit, 50)
    )


@router.get("/unread-count")
async def unread_count(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    svc = NotificationService(session)
    count = await svc.unread_count(user.id)
    return {"count": count}


@router.post("/read")
async def mark_read(
    body: ReadNotificationsRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = NotificationService(session)
    await svc.mark_read(
        body.notification_id, user.id
    )
    return {"status": "read"}


@router.post("/unread")
async def mark_unread(
    body: UnreadNotificationRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = NotificationService(session)
    await svc.mark_unread(
        body.notification_id, user.id
    )
    return {"status": "unread"}


@router.post("/read-all")
async def mark_all_read(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = NotificationService(session)
    await svc.mark_all_read(user.id)
    return {"status": "all_read"}


@router.delete(
    "/{notification_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_notification(
    notification_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    svc = NotificationService(session)
    deleted = await svc.delete(notification_id, user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
