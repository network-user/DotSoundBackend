from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.redis import get_redis_client

_KEY_PREFIX = "artist_catalog_sync:"
_TTL_RUNNING = 7200
_TTL_RESULT = 259200

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _key(artist_id: int) -> str:
    return f"{_KEY_PREFIX}{artist_id}"


async def set_running(
    artist_id: int,
    *,
    mode: str,
    soundcloud_album_id: int | None,
    detail: dict[str, Any] | None = None,
) -> None:
    redis = get_redis_client()
    payload: dict[str, Any] = {
        "state": "running",
        "mode": mode,
        "soundcloud_album_id": soundcloud_album_id,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if detail:
        payload["detail"] = detail
    await redis.set(
        _key(artist_id),
        json.dumps(payload),
        ex=_TTL_RUNNING,
    )


async def merge_running_detail(
    artist_id: int,
    detail_patch: dict[str, Any],
) -> None:
    try:
        redis = get_redis_client()
        key = _key(artist_id)
        raw = await redis.get(key)
        if not raw:
            return
        data = json.loads(raw)
        if not isinstance(data, dict):
            return
        if data.get("state") != "running":
            return
        cur = data.get("detail")
        merged: dict[str, Any] = (
            dict(cur) if isinstance(cur, dict) else {}
        )
        merged.update(detail_patch)
        data["detail"] = merged
        data["updated_at"] = datetime.now(UTC).isoformat()
        ttl = await redis.ttl(key)
        ex = ttl if ttl and ttl > 0 else _TTL_RUNNING
        await redis.set(key, json.dumps(data), ex=ex)
    except Exception as exc:
        logger.warning(
            "artist_catalog_sync_progress_merge_failed",
            artist_id=artist_id,
            error=str(exc),
        )


async def set_success(
    artist_id: int,
    *,
    mode: str,
    soundcloud_album_id: int | None,
    detail: dict[str, Any],
) -> None:
    redis = get_redis_client()
    payload: dict[str, Any] = {
        "state": "success",
        "mode": mode,
        "soundcloud_album_id": soundcloud_album_id,
        "detail": detail,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    await redis.set(
        _key(artist_id),
        json.dumps(payload),
        ex=_TTL_RESULT,
    )


async def set_error(
    artist_id: int,
    *,
    mode: str,
    soundcloud_album_id: int | None,
    message: str,
) -> None:
    redis = get_redis_client()
    payload: dict[str, Any] = {
        "state": "error",
        "mode": mode,
        "soundcloud_album_id": soundcloud_album_id,
        "error": message[:2000],
        "updated_at": datetime.now(UTC).isoformat(),
    }
    await redis.set(
        _key(artist_id),
        json.dumps(payload),
        ex=_TTL_RESULT,
    )


async def get_snapshot(artist_id: int) -> dict[str, Any] | None:
    redis = get_redis_client()
    raw = await redis.get(_key(artist_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
