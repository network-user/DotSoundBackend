from __future__ import annotations

import structlog
from dotsound_private_core.services.abuse import (
    TOR_LIST_URL,
    TOR_REDIS_KEY,
    TOR_REFRESH_TTL,
)

from app.core.redis import get_redis_client

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


async def refresh_tor_exit_nodes() -> int:
    import httpx

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

    r = get_redis_client()
    pipe = r.pipeline()
    pipe.delete(TOR_REDIS_KEY)
    for ip in ips:
        pipe.sadd(TOR_REDIS_KEY, ip)
    pipe.expire(TOR_REDIS_KEY, TOR_REFRESH_TTL)
    await pipe.execute()

    logger.info(
        "tor_exit_nodes_refreshed", count=len(ips)
    )
    return len(ips)


async def is_tor_exit_node(ip: str) -> bool:
    r = get_redis_client()
    result = await r.sismember(TOR_REDIS_KEY, ip)
    return bool(result)
