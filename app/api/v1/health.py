import time

import structlog
from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import AsyncSessionLocal
from app.schemas.common import (
    ComponentHealth,
    DeepHealthResponse,
    HealthResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

router = APIRouter(
    prefix="/health", tags=["health"]
)


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe: returns immediately."""
    return HealthResponse(status="ok")


async def _ping_db() -> ComponentHealth:
    start = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return ComponentHealth(
            status="ok",
            latency_ms=round(
                (time.perf_counter() - start) * 1000,
                2,
            ),
        )
    except Exception as exc:
        logger.warning(
            "health_db_failed",
            error=type(exc).__name__,
        )
        return ComponentHealth(
            status="error",
            detail=type(exc).__name__,
        )


async def _ping_redis() -> ComponentHealth:
    start = time.perf_counter()
    try:
        from app.core.redis import get_redis

        redis = await get_redis()
        await redis.ping()
        return ComponentHealth(
            status="ok",
            latency_ms=round(
                (time.perf_counter() - start) * 1000,
                2,
            ),
        )
    except Exception as exc:
        logger.warning(
            "health_redis_failed",
            error=type(exc).__name__,
        )
        return ComponentHealth(
            status="error",
            detail=type(exc).__name__,
        )


async def _ping_s3() -> ComponentHealth:
    start = time.perf_counter()
    try:
        from app.core.s3 import get_s3_client
        from app.config import settings

        async with get_s3_client() as client:
            await client.head_bucket(
                Bucket=settings.minio_bucket
            )
        return ComponentHealth(
            status="ok",
            latency_ms=round(
                (time.perf_counter() - start) * 1000,
                2,
            ),
        )
    except Exception as exc:
        logger.warning(
            "health_s3_failed",
            error=type(exc).__name__,
        )
        return ComponentHealth(
            status="error",
            detail=type(exc).__name__,
        )


@router.get(
    "/deep", response_model=DeepHealthResponse
)
async def health_deep() -> DeepHealthResponse:
    """Deep health-check: probes Postgres, Redis and S3.

    Returns ``status="degraded"`` if any single component is
    failing and ``status="error"`` if every component is down.
    The body always lists every component so external monitors
    can pick the right alert.
    """
    db = await _ping_db()
    redis = await _ping_redis()
    s3 = await _ping_s3()

    components = {
        "db": db,
        "redis": redis,
        "s3": s3,
    }
    statuses = {c.status for c in components.values()}
    if statuses == {"ok"}:
        overall = "ok"
    elif statuses == {"error"}:
        overall = "error"
    else:
        overall = "degraded"
    return DeepHealthResponse(
        status=overall,
        components=components,
    )
