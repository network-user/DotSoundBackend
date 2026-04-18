from __future__ import annotations

import asyncio
import weakref
from typing import TYPE_CHECKING

from redis.asyncio import ConnectionPool, Redis

from app.config import settings

if TYPE_CHECKING:
    from redis.asyncio.client import PubSub


_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Redis]" = (
    weakref.WeakKeyDictionary()
)
_pools: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, ConnectionPool]" = (
    weakref.WeakKeyDictionary()
)


def get_redis_client() -> Redis:
    """Return a loop-local shared Redis client.

    Uses one connection pool per running event loop. This lets a
    single process reuse connections without tying them to a stale
    loop after shutdown/reload. Safe to call from request handlers
    and Taskiq workers. Callers must not ``aclose()`` it directly.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    client = _clients.get(loop)
    if client is None:
        pool = _pools.get(loop)
        if pool is None:
            pool = ConnectionPool.from_url(
                settings.redis_url,
                decode_responses=True,
                max_connections=32,
            )
            _pools[loop] = pool
        client = Redis(connection_pool=pool)
        _clients[loop] = client
    return client


async def get_pubsub() -> "PubSub":
    return get_redis_client().pubsub()


async def close_redis() -> None:
    """Close the current loop's client + pool on shutdown."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    client = _clients.pop(loop, None)
    if client is not None:
        try:
            await client.aclose()
        except Exception:
            pass
    pool = _pools.pop(loop, None)
    if pool is not None:
        try:
            await pool.aclose()
        except Exception:
            pass
