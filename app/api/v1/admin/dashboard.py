"""Admin dashboard endpoints (KPIs, timeseries proxy)."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db,
    require_admin_session,
)
from app.models.user import User
from app.services.admin_dashboard_service import (
    collect_admin_stats,
    collect_stats,
    collect_track_stats,
    collect_overview,
)
from app.services.container_health_service import (
    get_container_summary,
)
from app.services.prometheus_service import (
    ALLOWED_METRICS,
    PrometheusServiceError,
    query_range,
)

router = APIRouter(prefix="/dashboard", tags=["admin-dashboard"])


@router.get("/overview")
async def overview(
    _admin: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await collect_overview(session)


@router.get("/stats")
async def stats(
    period: str = Query("today", pattern="^(today|7d|30d|all)$"),
    _admin: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await collect_stats(session, period=period)


@router.get("/track-stats")
async def track_stats(
    period: str = Query("today", pattern="^(today|7d|30d|all)$"),
    _admin: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await collect_track_stats(session, period=period)


@router.get("/admin-stats")
async def admin_stats(
    period: str = Query("today", pattern="^(today|7d|30d|all)$"),
    _admin: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await collect_admin_stats(session, period=period)


@router.get("/containers")
async def container_overview(
    _admin: User = Depends(require_admin_session),
) -> dict[str, Any]:
    return await get_container_summary()


@router.get("/timeseries")
async def timeseries(
    metric: str = Query(..., min_length=2, max_length=64),
    minutes: int = Query(60, ge=1, le=10_080),
    step_seconds: int = Query(30, ge=5, le=3600),
    _admin: User = Depends(require_admin_session),
) -> dict[str, Any]:
    """Prometheus range-query proxy for KPI charts.

    The ``metric`` argument is one of the whitelisted aliases from
    ``app.services.prometheus_service.ALLOWED_METRICS``; raw PromQL
    is rejected.
    """
    if metric not in ALLOWED_METRICS:
        raise HTTPException(
            status_code=400,
            detail="metric not allowed",
        )
    end = time.time()
    start = end - minutes * 60
    try:
        return await query_range(
            metric=metric,
            start=start,
            end=end,
            step_seconds=step_seconds,
        )
    except PrometheusServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/metrics-allowlist")
async def metrics_allowlist(
    _admin: User = Depends(require_admin_session),
) -> dict[str, Any]:
    return {
        "metrics": sorted(ALLOWED_METRICS.keys()),
    }
