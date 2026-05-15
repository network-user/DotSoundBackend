"""System resource snapshots for the admin dashboard."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from app.config import settings
from app.core.redis import get_redis_client

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

HISTORY_KEY = "admin:system_resources:history"


@dataclass(frozen=True)
class CpuTimes:
    idle: int
    total: int


def _pct(used: float, total: float) -> float | None:
    if total <= 0:
        return None
    return round((used / total) * 100.0, 2)


def _read_cpu_times() -> CpuTimes | None:
    try:
        line = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
        parts = line.split()
        if parts[0] != "cpu":
            return None
        values = [int(value) for value in parts[1:]]
        if len(values) < 4:
            return None
        idle = values[3]
        if len(values) > 4:
            idle += values[4]
        return CpuTimes(idle=idle, total=sum(values))
    except (OSError, IndexError, ValueError):
        return None


def _sample_cpu_pct() -> float | None:
    first = _read_cpu_times()
    if first is None:
        return None
    delay = max(0.05, min(1.0, settings.system_resource_cpu_sample_seconds))
    time.sleep(delay)
    second = _read_cpu_times()
    if second is None:
        return None
    total_delta = second.total - first.total
    idle_delta = second.idle - first.idle
    if total_delta <= 0:
        return 0.0
    busy = max(0, total_delta - idle_delta)
    return round((busy / total_delta) * 100.0, 2)


def _read_load_avg() -> dict[str, float | None]:
    getloadavg = getattr(os, "getloadavg", None)
    if not callable(getloadavg):
        return {"one": None, "five": None, "fifteen": None}
    try:
        one, five, fifteen = getloadavg()
    except OSError:
        return {"one": None, "five": None, "fifteen": None}
    return {
        "one": round(one, 2),
        "five": round(five, 2),
        "fifteen": round(fifteen, 2),
    }


def _read_memory() -> dict[str, int | float | None]:
    try:
        raw = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return {
            "total_bytes": None,
            "used_bytes": None,
            "available_bytes": None,
            "used_pct": None,
        }

    values: dict[str, int] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        parts = rest.strip().split()
        if not parts:
            continue
        try:
            values[key] = int(parts[0]) * 1024
        except ValueError:
            continue

    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if total is None or available is None:
        return {
            "total_bytes": None,
            "used_bytes": None,
            "available_bytes": None,
            "used_pct": None,
        }
    used = max(0, total - available)
    return {
        "total_bytes": total,
        "used_bytes": used,
        "available_bytes": available,
        "used_pct": _pct(used, total),
    }


def _read_storage() -> dict[str, int | float | str | None]:
    path = settings.system_resource_disk_path or "/"
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return {
            "path": path,
            "total_bytes": None,
            "used_bytes": None,
            "free_bytes": None,
            "used_pct": None,
        }
    return {
        "path": path,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_pct": _pct(usage.used, usage.total),
    }


def _collect_sync() -> dict[str, Any]:
    return {
        "ts": int(time.time()),
        "source": "procfs",
        "cpu_pct": _sample_cpu_pct(),
        "load_avg": _read_load_avg(),
        "memory": _read_memory(),
        "storage": _read_storage(),
    }


def _history_item(snapshot: dict[str, Any]) -> dict[str, Any]:
    memory = snapshot.get("memory") or {}
    storage = snapshot.get("storage") or {}
    return {
        "ts": int(snapshot.get("ts") or 0),
        "cpu_pct": snapshot.get("cpu_pct"),
        "memory_used_pct": memory.get("used_pct"),
        "storage_used_pct": storage.get("used_pct"),
    }


async def _store_snapshot(snapshot: dict[str, Any]) -> None:
    ts = int(snapshot.get("ts") or time.time())
    item = json.dumps(_history_item(snapshot), separators=(",", ":"))
    cutoff = ts - max(60, int(settings.system_resource_history_ttl_seconds))
    redis = get_redis_client()
    await redis.zadd(HISTORY_KEY, {item: ts})
    await redis.zremrangebyscore(HISTORY_KEY, 0, cutoff)


async def collect_system_resource_snapshot(
    *,
    store: bool = True,
) -> dict[str, Any]:
    snapshot = await asyncio.to_thread(_collect_sync)
    if store:
        try:
            await _store_snapshot(snapshot)
        except Exception:
            logger.exception("system_resource_snapshot_store_failed")
    return snapshot


async def get_system_resource_summary(
    *,
    minutes: int = 60,
) -> dict[str, Any]:
    current = await collect_system_resource_snapshot(store=True)
    end = int(time.time())
    start = end - max(1, min(10_080, minutes)) * 60
    history: list[dict[str, Any]] = []
    try:
        rows = await get_redis_client().zrangebyscore(HISTORY_KEY, start, end)
        for raw in rows:
            try:
                text = raw if isinstance(raw, str) else raw.decode()
                item = json.loads(text)
                if isinstance(item, dict):
                    history.append(item)
            except (TypeError, ValueError, UnicodeError):
                continue
    except Exception:
        logger.exception("system_resource_history_read_failed")
    if not history:
        history = [_history_item(current)]
    return {
        "generated_at": int(time.time()),
        "current": current,
        "history": history,
    }


async def system_resource_sampler_loop(stop: asyncio.Event) -> None:
    interval = max(5, int(settings.system_resource_sample_interval_seconds))
    while not stop.is_set():
        try:
            await collect_system_resource_snapshot(store=True)
        except Exception:
            logger.exception("system_resource_sampler_failed")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval)


__all__ = [
    "HISTORY_KEY",
    "collect_system_resource_snapshot",
    "get_system_resource_summary",
    "system_resource_sampler_loop",
]
