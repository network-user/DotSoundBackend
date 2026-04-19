"""Admin dashboard endpoints (KPIs, timeseries proxy)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db,
    require_admin_session,
)
from app.models.user import User
from app.services.admin_dashboard_service import (
    collect_overview,
)
from app.services.container_health_service import (
    get_container_summary,
)

router = APIRouter(prefix="/dashboard", tags=["admin-dashboard"])


@router.get("/overview")
async def overview(
    _admin: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await collect_overview(session)


@router.get("/containers")
async def container_overview(
    _admin: User = Depends(require_admin_session),
) -> dict[str, Any]:
    return await get_container_summary()
