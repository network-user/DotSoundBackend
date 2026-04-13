from __future__ import annotations

import structlog
from dotsound_private_core.services.abuse import (
    TOR_LIST_URL,
    TOR_REDIS_KEY,
    TOR_REFRESH_TTL,
)

from app.config import settings

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


async def refresh_tor_exit_nodes() -> int:
    import httpx
    import redis.asyncio as aioredis

    try:
        async with httpx.AsyncClient(
            timeout=30
        ) as client:
            resp = await client.get(TOR_LIST_URL)
            resp.raise_for_status()
    except Exception:
        logger.exception("tor_list_fetch_failed")
        return 0

    ips: list[str] = []
    for line in resp.text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            ips.append(line)

    if not ips:
        logger.warning("tor_list_empty")
        return 0

    r = aioredis.from_url(settings.redis_url)
    pipe = r.pipeline()
    pipe.delete(TOR_REDIS_KEY)
    for ip in ips:
        pipe.sadd(TOR_REDIS_KEY, ip)
    pipe.expire(TOR_REDIS_KEY, TOR_REFRESH_TTL)
    await pipe.execute()
    await r.aclose()

    logger.info(
        "tor_exit_nodes_refreshed", count=len(ips)
    )
    return len(ips)


async def is_tor_exit_node(ip: str) -> bool:
    import redis.asyncio as aioredis

    r = aioredis.from_url(settings.redis_url)
    result = await r.sismember(TOR_REDIS_KEY, ip)
    await r.aclose()
    return bool(result)
