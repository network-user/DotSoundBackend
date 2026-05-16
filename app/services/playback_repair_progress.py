from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.redis import get_redis_client

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_KEY_PREFIX = "playback_repair:progress:"
_TTL_RUNNING = 7200
_TTL_RESULT = 86400

_PUBLIC_STAGES: frozenset[str] = frozenset(
    {
        "queued",
        "loading_track",
        "skipped",
        "verifying_current_source",
        "refreshing_source",
        "verifying_refreshed_source",
        "clearing_health",
        "repaired",
        "unresolved",
        "not_found",
        "error",
        "cancelled",
        "processing",
    }
)

_TERMINAL_STAGES: frozenset[str] = frozenset(
    {
        "skipped",
        "repaired",
        "unresolved",
        "not_found",
        "error",
        "cancelled",
    }
)


def new_progress_id() -> str:
    return uuid.uuid4().hex


def public_stage(stage: str) -> str:
    return stage if stage in _PUBLIC_STAGES else "processing"


def _key(progress_id: str) -> str:
    return f"{_KEY_PREFIX}{progress_id}"


async def set_progress(
    progress_id: str,
    *,
    stage: str,
    track_id: int | None = None,
    log_line: str | None = None,
    result: dict[str, Any] | None = None,
) -> None:
    redis = get_redis_client()
    key = _key(progress_id)
    raw = await redis.get(key)
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}

    now = datetime.now(UTC).isoformat()
    safe_stage = public_stage(stage)
    logs = list(data.get("logs") or [])
    if log_line:
        logs = (logs + [log_line])[-100:]
    data.update(
        {
            "progress_id": progress_id,
            "track_id": track_id,
            "stage": safe_stage,
            "state": (
                "finished"
                if safe_stage in _TERMINAL_STAGES
                else "running"
            ),
            "updated_at": now,
            "logs": logs,
        }
    )
    data.setdefault("created_at", now)
    if result is not None:
        data["result"] = result

    ttl = _TTL_RESULT if safe_stage in _TERMINAL_STAGES else _TTL_RUNNING
    await redis.set(key, json.dumps(data, default=str), ex=ttl)


async def safe_set_progress(
    progress_id: str | None,
    *,
    stage: str,
    track_id: int | None = None,
    log_line: str | None = None,
    result: dict[str, Any] | None = None,
) -> None:
    if not progress_id:
        return
    try:
        await set_progress(
            progress_id,
            stage=stage,
            track_id=track_id,
            log_line=log_line,
            result=result,
        )
    except Exception as exc:
        logger.warning(
            "playback_repair_progress_write_failed",
            progress_id=progress_id,
            stage=stage,
            error=str(exc),
        )


async def get_progress(progress_id: str) -> dict[str, Any] | None:
    raw = await get_redis_client().get(_key(progress_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


async def get_many_progress(
    progress_ids: list[str],
) -> dict[str, dict[str, Any]]:
    unique_ids = list(dict.fromkeys(pid for pid in progress_ids if pid))
    if not unique_ids:
        return {}
    redis = get_redis_client()
    values = await redis.mget([_key(pid) for pid in unique_ids])
    out: dict[str, dict[str, Any]] = {}
    for progress_id, raw in zip(unique_ids, values, strict=False):
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            out[progress_id] = data
    return out
