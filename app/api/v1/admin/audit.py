"""Admin audit-log endpoints (read + CSV export)."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db,
    require_capability,
    require_step_up,
)
from app.models.login_history import LoginHistory
from app.models.user import User
from app.repositories.admin_action_log import (
    AdminActionLogRepository,
)

router = APIRouter(prefix="/audit", tags=["admin-audit"])


@router.get("/")
async def list_audit(
    user_id: int | None = Query(None),
    action: str | None = Query(None, max_length=64),
    target_type: str | None = Query(None, max_length=64),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_capability("audit.view")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repo = AdminActionLogRepository(session)
    rows, total = await repo.list_paginated(
        user_id=user_id,
        action=action,
        target_type=target_type,
        since=since,
        until=until,
        page=page,
        size=size,
    )
    return {
        "items": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "ip": row.ip,
                "meta": row.meta,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/export.csv")
async def export_csv(
    user_id: int | None = Query(None),
    action: str | None = Query(None, max_length=64),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    _admin: User = Depends(require_step_up("audit.export")),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    repo = AdminActionLogRepository(session)
    rows = await repo.stream_for_export(
        user_id=user_id,
        action=action,
        since=since,
        until=until,
    )

    def _iter() -> Any:  # noqa: ANN401
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "id",
                "user_id",
                "action",
                "target_type",
                "target_id",
                "ip",
                "meta",
                "created_at",
            ]
        )
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for row in rows:
            writer.writerow(
                [
                    row.id,
                    row.user_id,
                    row.action,
                    row.target_type or "",
                    row.target_id or "",
                    row.ip or "",
                    ("" if row.meta is None else str(row.meta)),
                    row.created_at.isoformat() if row.created_at else "",
                ]
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(
        _iter(),
        media_type="text/csv",
        headers={
            "Content-Disposition": ("attachment; " "filename=admin-audit.csv"),
        },
    )


@router.get("/login-history")
async def login_history(
    user_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    _admin: User = Depends(require_capability("audit.view")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """User login history (replaces inline SQL from
    ``api/v1/users.py:get_login_history`` for admin use).

    Without ``user_id`` returns most recent logins across all
    users; with ``user_id`` filters to that user.
    """
    query = select(LoginHistory)
    if user_id is not None:
        query = query.where(LoginHistory.user_id == user_id)
    query = query.order_by(desc(LoginHistory.created_at)).limit(limit)
    result = await session.execute(query)
    rows = list(result.scalars().all())
    return {
        "items": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "ip": row.ip,
                "device": row.device,
                "login_type": row.login_type,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "user_id": user_id,
        "count": len(rows),
    }
