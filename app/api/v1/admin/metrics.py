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


def _empty_instant(reason: str) -> dict[str, Any]:
    return {
        "data": {"resultType": "vector", "result": []},
        "source_status": "disabled",
        "source_reason": reason,
    }


def _empty_range(reason: str) -> dict[str, Any]:
    return {
        "data": {"resultType": "matrix", "result": []},
        "source_status": "disabled",
        "source_reason": reason,
    }


@router.get("/instant")
async def instant(
    name: str = Query(..., min_length=2, max_length=64),
    _admin: User = Depends(require_capability("metrics.view")),
) -> dict[str, Any]:
    from app.config import settings

    if not settings.prometheus_url:
        return _empty_instant("prometheus_not_configured")
    try:
        result = await query_instant(metric=name)
    except PrometheusServiceError as exc:
        msg = str(exc)
        if "not configured" in msg:
            return _empty_instant("prometheus_not_configured")
        if "not allowed" in msg:
            raise HTTPException(status_code=400, detail=msg) from exc
        return {
            **_empty_instant(msg),
            "source_status": "error",
        }
    result["source_status"] = "available"
    return result


@router.get("/range")
async def range_query(
    name: str = Query(..., min_length=2, max_length=64),
    minutes: int = Query(60, ge=1, le=10_080),
    step_seconds: int = Query(30, ge=5, le=3600),
    _admin: User = Depends(require_capability("metrics.view")),
) -> dict[str, Any]:
    from app.config import settings

    if not settings.prometheus_url:
        return _empty_range("prometheus_not_configured")
    end = time.time()
    start = end - minutes * 60
    try:
        result = await query_range(
            metric=name,
            start=start,
            end=end,
            step_seconds=step_seconds,
        )
    except PrometheusServiceError as exc:
        msg = str(exc)
        if "not configured" in msg:
            return _empty_range("prometheus_not_configured")
        if "not allowed" in msg:
            raise HTTPException(status_code=400, detail=msg) from exc
        return {
            **_empty_range(msg),
            "source_status": "error",
        }
    result["source_status"] = "available"
    return result
