from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.core.redis import get_redis_client

_KEY_PREFIX = "artist_catalog_sync:"
_TTL_RUNNING = 7200
_TTL_RESULT = 259200


def _key(artist_id: int) -> str:
    return f"{_KEY_PREFIX}{artist_id}"


async def set_running(
    artist_id: int,
    *,
    mode: str,
    soundcloud_album_id: int | None,
) -> None:
    redis = get_redis_client()
    payload: dict[str, Any] = {
        "state": "running",
        "mode": mode,
        "soundcloud_album_id": soundcloud_album_id,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    await redis.set(
        _key(artist_id),
        json.dumps(payload),
        ex=_TTL_RUNNING,
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
