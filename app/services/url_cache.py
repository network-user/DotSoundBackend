from __future__ import annotations

import hashlib
import json

from app.core.redis import get_redis_client

CACHE_KEY_SC = "stream_url:sc:{key}"
CACHE_KEY_BC = "stream_url:bc:{key}"


def _build_key(template: str, identifier: str) -> str:
    h = hashlib.sha256(identifier.encode()).hexdigest()[:32]
    return template.format(key=h)


async def get_cached_stream(
    template: str, identifier: str
) -> tuple[str, str] | None:
    raw = await get_redis_client().get(_build_key(template, identifier))
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        return data["url"], data["protocol"]
    except Exception:
        return None


async def set_cached_stream(
    template: str,
    identifier: str,
    url: str,
    protocol: str,
    ttl: int,
) -> None:
    await get_redis_client().set(
        _build_key(template, identifier),
        json.dumps({"url": url, "protocol": protocol}),
        ex=ttl,
    )
