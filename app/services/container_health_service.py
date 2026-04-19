"""Docker container health probe.

Reads container state through the Docker SDK over the mounted
socket and caches the result in Redis (loop-local pool). Falls
back to ``"degraded": []`` when the SDK or the socket is
unavailable so the admin UI keeps working.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC
from typing import Any

import structlog

from app.config import settings
from app.core.redis import get_redis_client

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

CACHE_KEY = "admin:containers:snapshot"
CACHE_TTL_SECONDS = 15

PROJECT_CONTAINERS = (
    "postgres",
    "redis",
    "minio",
    "backend",
    "worker",
    "frontend",
    "prometheus",
    "loki",
    "grafana",
    "tempo",
    "promtail",
    "otel-collector",
    "cadvisor",
)


@dataclass
class ContainerStatus:
    name: str
    status: str
    health: str
    uptime_seconds: int | None
    restart_count: int
    cpu_pct: float | None
    mem_mb: float | None
    image: str | None


def _matches_project(name: str) -> bool:
    lowered = name.lower()
    return any(keyword in lowered for keyword in PROJECT_CONTAINERS)


def _stats_to_cpu_pct(
    stats: dict[str, Any],
) -> float | None:
    try:
        cpu = stats["cpu_stats"]
        precpu = stats["precpu_stats"]
        cpu_total = cpu["cpu_usage"]["total_usage"]
        pre_total = precpu["cpu_usage"]["total_usage"]
        sys_total = cpu["system_cpu_usage"]
        pre_sys = precpu["system_cpu_usage"]
        cpu_delta = cpu_total - pre_total
        sys_delta = sys_total - pre_sys
        online = cpu.get("online_cpus") or len(
            cpu["cpu_usage"].get("percpu_usage", []) or [1]
        )
        if sys_delta <= 0 or cpu_delta <= 0:
            return 0.0
        return round(
            (cpu_delta / sys_delta) * online * 100.0,
            2,
        )
    except (KeyError, TypeError, ZeroDivisionError):
        return None


def _stats_to_mem_mb(
    stats: dict[str, Any],
) -> float | None:
    try:
        usage = stats["memory_stats"]["usage"]
        cache = stats["memory_stats"].get("stats", {}).get("cache", 0)
        return round((usage - cache) / (1024.0 * 1024.0), 2)
    except (KeyError, TypeError):
        return None


def _collect_sync() -> list[dict[str, Any]]:
    try:
        import docker
    except ImportError:
        logger.warning("docker_sdk_missing")
        return []
    try:
        client = docker.DockerClient(
            base_url=(f"unix://{settings.docker_socket_path}")
        )
        containers = client.containers.list(all=True)
    except Exception as exc:
        logger.warning(
            "docker_socket_unavailable",
            error=type(exc).__name__,
        )
        return []

    results: list[dict[str, Any]] = []
    for cont in containers:
        name = (cont.name or "").strip("/")
        if not _matches_project(name):
            continue
        try:
            attrs = cont.attrs
            state = attrs.get("State", {})
            health_obj = state.get("Health", {})
            health = health_obj.get("Status", "unknown")
            started_at = state.get("StartedAt")
            uptime: int | None = None
            if started_at:
                try:
                    from datetime import (
                        datetime,
                    )

                    dt = datetime.fromisoformat(
                        started_at.replace("Z", "+00:00").split(".")[0]
                        + "+00:00"
                    )
                    uptime = int((datetime.now(UTC) - dt).total_seconds())
                except Exception:
                    uptime = None
            restart_count = int(state.get("RestartCount", 0))
            try:
                stats = cont.stats(stream=False)
            except Exception:
                stats = {}
            results.append(
                asdict(
                    ContainerStatus(
                        name=name,
                        status=str(state.get("Status", "unknown")),
                        health=str(health or "none"),
                        uptime_seconds=uptime,
                        restart_count=restart_count,
                        cpu_pct=_stats_to_cpu_pct(stats),
                        mem_mb=_stats_to_mem_mb(stats),
                        image=str(attrs.get("Config", {}).get("Image") or ""),
                    )
                )
            )
        except Exception:
            logger.exception(
                "container_inspect_failed",
                name=name,
            )
    with contextlib.suppress(Exception):
        client.close()
    return results


async def get_container_snapshot(
    *, force_refresh: bool = False
) -> list[dict[str, Any]]:
    redis = get_redis_client()
    if not force_refresh:
        cached = await redis.get(CACHE_KEY)
        if cached:
            try:
                return list(
                    json.loads(
                        cached if isinstance(cached, str) else cached.decode()
                    )
                )
            except Exception:
                pass
    snapshot = await asyncio.to_thread(_collect_sync)
    payload = json.dumps(snapshot)
    try:
        await redis.setex(
            CACHE_KEY,
            CACHE_TTL_SECONDS,
            payload,
        )
    except Exception:
        logger.exception("container_snapshot_cache_failed")
    return snapshot


async def get_container_summary() -> dict[str, Any]:
    snap = await get_container_snapshot()
    counts = {
        "ok": 0,
        "warning": 0,
        "error": 0,
        "unknown": 0,
    }
    for item in snap:
        status = str(item.get("status", "unknown"))
        health = str(item.get("health", "unknown"))
        if status == "running" and health in {
            "healthy",
            "none",
        }:
            counts["ok"] += 1
        elif (
            status == "running" and health == "unhealthy"
        ) or status == "exited":
            counts["error"] += 1
        elif status == "running":
            counts["warning"] += 1
        else:
            counts["unknown"] += 1
    return {
        "counts": counts,
        "total": len(snap),
        "generated_at": int(time.time()),
        "containers": snap,
    }


__all__ = [
    "PROJECT_CONTAINERS",
    "ContainerStatus",
    "get_container_snapshot",
    "get_container_summary",
]
