"""Admin logs endpoints (Loki proxy + live tail).

LogQL queries are constructed from a small whitelist of label
selectors so a logged-in admin cannot run arbitrary queries.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import require_capability
from app.models.user import User
from app.services.loki_service import (
    ALLOWED_LABELS,
    ALLOWED_LEVELS,
    LokiServiceError,
    query_range,
)

router = APIRouter(prefix="/logs", tags=["admin-logs"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.get("/labels")
async def list_labels(
    _admin: User = Depends(require_capability("logs.view")),
) -> dict[str, Any]:
    return {
        "labels": sorted(ALLOWED_LABELS),
        "levels": sorted(ALLOWED_LEVELS),
    }


@router.get("/query")
async def query_logs(
    container: str | None = Query(None),
    level: str | None = Query(None),
    service: str | None = Query(None),
    contains: str | None = Query(None, max_length=256),
    minutes: int = Query(15, ge=1, le=720),
    limit: int = Query(200, ge=1, le=1000),
    _admin: User = Depends(require_capability("logs.view")),
) -> dict[str, Any]:
    selectors: dict[str, str] = {}
    if container:
        selectors["container"] = container
    if service:
        selectors["service"] = service
    if level:
        selectors["level"] = level
    if not selectors:
        selectors["service"] = "dotsound-backend"

    end_ns = int(time.time() * 1_000_000_000)
    start_ns = end_ns - minutes * 60 * 1_000_000_000
    try:
        rows = await query_range(
            selectors=selectors,
            contains=contains,
            start_ns=start_ns,
            end_ns=end_ns,
            limit=limit,
        )
    except LokiServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "items": rows,
        "selectors": selectors,
        "minutes": minutes,
        "count": len(rows),
    }
