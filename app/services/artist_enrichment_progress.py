"""Redis-backed progress tracking for artist enrichment tasks.

Mirrors the lyrics-worker progress helpers so the UI can poll the
current stage and a bounded log history. Stage labels that cross the
backend↔frontend boundary are checked against an allow-list; anything
else is collapsed to ``processing``.
"""
from __future__ import annotations

import json
import time

from redis.asyncio import Redis

from app.config import settings

_PROGRESS_KEY_PREFIX = "artist_enrich:progress:"
_PROGRESS_TTL = 600

_PUBLIC_STAGES: frozenset[str] = frozenset(
    {
        "queued",
        "searching",
        "fetching_details",
        "merging",
        "saving",
        "done",
        "not_found",
        "error",
        "processing",
    }
)


def opaque_stage(stage: str) -> str:
    return stage if stage in _PUBLIC_STAGES else "processing"


async def _get_redis() -> Redis:  # type: ignore[type-arg]
    return Redis.from_url(
        settings.redis_url, decode_responses=True
    )


def _elapsed_line(t0: float, msg: str) -> str:
    return f"[{time.monotonic() - t0:.1f}s] {msg}"


async def set_progress(
    progress_id: str,
    stage: str,
    log_line: str | None = None,
) -> None:
    redis = await _get_redis()
    try:
        key = f"{_PROGRESS_KEY_PREFIX}{progress_id}"
        raw = await redis.get(key)
        data = (
            json.loads(raw)
            if raw
            else {"stage": stage, "logs": []}
        )
        data["stage"] = stage
        if log_line:
            logs = list(data.get("logs") or [])
            data["logs"] = (logs + [log_line])[-100:]
        await redis.set(
            key, json.dumps(data), ex=_PROGRESS_TTL
        )
    finally:
        await redis.aclose()


async def append_log(
    progress_id: str, log_line: str
) -> None:
    redis = await _get_redis()
    try:
        key = f"{_PROGRESS_KEY_PREFIX}{progress_id}"
        raw = await redis.get(key)
        data = (
            json.loads(raw)
            if raw
            else {"stage": "queued", "logs": []}
        )
        logs = list(data.get("logs") or [])
        data["logs"] = (logs + [log_line])[-100:]
        await redis.set(
            key, json.dumps(data), ex=_PROGRESS_TTL
        )
    finally:
        await redis.aclose()


async def get_progress(
    progress_id: str,
) -> dict[str, object] | None:
    redis = await _get_redis()
    try:
        raw = await redis.get(
            f"{_PROGRESS_KEY_PREFIX}{progress_id}"
        )
        if not raw:
            return None
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    finally:
        await redis.aclose()
