"""Admin metrics endpoints (Prometheus proxy).

Only whitelisted PromQL expressions are exposed via the metric
``name``; raw PromQL is never accepted.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import require_capability
from app.models.user import User
from app.services.prometheus_service import (
    ALLOWED_METRICS,
    PrometheusServiceError,
    query_instant,
    query_range,
)

router = APIRouter(prefix="/metrics", tags=["admin-metrics"])


@router.get("/list")
async def list_metrics(
    _admin: User = Depends(require_capability("metrics.view")),
) -> dict[str, Any]:
    return {"metrics": sorted(ALLOWED_METRICS.keys())}


@router.get("/instant")
async def instant(
    name: str = Query(..., min_length=2, max_length=64),
    _admin: User = Depends(require_capability("metrics.view")),
) -> dict[str, Any]:
    try:
        return await query_instant(metric=name)
    except PrometheusServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/range")
async def range_query(
    name: str = Query(..., min_length=2, max_length=64),
    minutes: int = Query(60, ge=1, le=10_080),
    step_seconds: int = Query(30, ge=5, le=3600),
    _admin: User = Depends(require_capability("metrics.view")),
) -> dict[str, Any]:
    end = time.time()
    start = end - minutes * 60
    try:
        return await query_range(
            metric=name,
            start=start,
            end=end,
            step_seconds=step_seconds,
        )
    except PrometheusServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
