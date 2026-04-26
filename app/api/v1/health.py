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
        from app.config import settings
        from app.core.s3 import get_s3_client

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


async def _ping_loki() -> ComponentHealth | None:
    from app.config import settings

    if not settings.loki_url:
        return None
    start = time.perf_counter()
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=3.0
        ) as client:
            response = await client.get(
                settings.loki_url.rstrip("/")
                + "/ready"
            )
            response.raise_for_status()
        return ComponentHealth(
            status="ok",
            latency_ms=round(
                (time.perf_counter() - start) * 1000,
                2,
            ),
        )
    except Exception as exc:
        return ComponentHealth(
            status="error",
            detail=type(exc).__name__,
        )


async def _ping_prometheus() -> ComponentHealth | None:
    from app.config import settings

    if not settings.prometheus_url:
        return None
    start = time.perf_counter()
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=3.0
        ) as client:
            response = await client.get(
                settings.prometheus_url.rstrip("/")
                + "/-/healthy"
            )
            response.raise_for_status()
        return ComponentHealth(
            status="ok",
            latency_ms=round(
                (time.perf_counter() - start) * 1000,
                2,
            ),
        )
    except Exception as exc:
        return ComponentHealth(
            status="error",
            detail=type(exc).__name__,
        )


async def _ping_taskiq() -> ComponentHealth:
    start = time.perf_counter()
    try:
        from app.core.tkq import broker

        if hasattr(broker, "startup"):
            pass
        from app.core.redis import get_redis_client

        redis = get_redis_client()
        await redis.ping()
        return ComponentHealth(
            status="ok",
            latency_ms=round(
                (time.perf_counter() - start) * 1000,
                2,
            ),
        )
    except Exception as exc:
        return ComponentHealth(
            status="error",
            detail=type(exc).__name__,
        )


@router.get(
    "/deep", response_model=DeepHealthResponse
)
async def health_deep() -> DeepHealthResponse:
    """Deep health-check across infra and observability.

    Always probes Postgres / Redis / S3 / Taskiq broker. Loki and
    Prometheus are probed only when their URLs are configured. The
    response is ``"ok"`` when every component is healthy,
    ``"error"`` when every component is failing, and
    ``"degraded"`` otherwise so external monitors can route alerts
    accordingly.
    """
    db = await _ping_db()
    redis = await _ping_redis()
    s3 = await _ping_s3()
    taskiq = await _ping_taskiq()

    components: dict[str, ComponentHealth] = {
        "db": db,
        "redis": redis,
        "s3": s3,
        "taskiq": taskiq,
    }
    loki = await _ping_loki()
    if loki is not None:
        components["loki"] = loki
    prom = await _ping_prometheus()
    if prom is not None:
        components["prometheus"] = prom

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
