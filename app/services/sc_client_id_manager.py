"""SC_CLIENT_ID lifecycle manager.

On app/worker startup call ``initialize()`` to populate the
process-local cache from Redis or by scraping SoundCloud JS bundles
directly.  ``SoundCloudService._client_id`` reads from ``get_sync()``
so the backend never stalls on a stale .env entry.

When SC returns 401, call ``on_auth_failure()`` to force a fresh
scrape, update Redis, and return the new credential.
"""

from __future__ import annotations

import re
from datetime import timedelta

import httpx
import structlog

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_REDIS_KEY = "sc:client_id:active"
_REDIS_TTL = timedelta(hours=72)

_SC_HOME = "https://soundcloud.com/"
_RE_SCRIPT_URL = re.compile(
    r'src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"'
)
_RE_CLIENT_IDS = (
    re.compile(r'client_id:"([a-zA-Z0-9_-]+)"'),
    re.compile(r"client_id:'([a-zA-Z0-9_-]+)'"),
)
_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_active: str = ""


def get_sync() -> str:
    """Sync read; returns cached ID or falls back to settings.sc_client_id."""
    return _active or settings.sc_client_id or ""


async def _scrape() -> str | None:
    """GET soundcloud.com → parse JS bundles → return client_id or None."""
    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        trust_env=False,
    ) as client:
        try:
            r = await client.get(_SC_HOME, headers=_HEADERS)
            r.raise_for_status()
        except Exception as exc:
            logger.error("sc_cid_scrape_home_failed", error=str(exc)[:200])
            return None

        script_urls = _RE_SCRIPT_URL.findall(r.text)
        if not script_urls:
            logger.error("sc_cid_scrape_no_scripts")
            return None

        logger.info("sc_cid_scrape_bundles_found", count=len(script_urls))
        for url in script_urls:
            try:
                rb = await client.get(url, headers=_HEADERS)
                rb.raise_for_status()
            except Exception:
                continue
            for pat in _RE_CLIENT_IDS:
                match = pat.search(rb.text)
                if match:
                    return match.group(1)

    logger.error("sc_cid_scrape_not_found_in_bundles")
    return None


async def _store_in_redis(client_id: str) -> None:
    from app.core.redis import get_redis_client

    try:
        redis = get_redis_client()
        await redis.set(
            _REDIS_KEY,
            client_id,
            ex=int(_REDIS_TTL.total_seconds()),
        )
        logger.info(
            "sc_cid_cached_in_redis",
            partial=client_id[:8] + "...",
            ttl_hours=int(_REDIS_TTL.total_seconds() // 3600),
        )
    except Exception as exc:
        logger.warning("sc_cid_redis_write_failed", error=str(exc)[:200])


async def initialize() -> str:
    """Populate the process-local cache from Redis or by scraping.

    Called once on app/worker startup.  Cheap if Redis already has a
    fresh value; otherwise performs a full scrape of SoundCloud JS
    bundles.
    """
    global _active

    from app.core.redis import get_redis_client

    try:
        redis = get_redis_client()
        cached = await redis.get(_REDIS_KEY)
        if cached:
            _active = str(cached)
            logger.info(
                "sc_cid_loaded_from_redis",
                partial=_active[:8] + "...",
            )
            return _active
    except Exception as exc:
        logger.warning("sc_cid_redis_read_failed", error=str(exc)[:200])

    fresh = await _scrape()
    if fresh:
        _active = fresh
        await _store_in_redis(fresh)
        return fresh

    fallback = settings.sc_client_id or ""
    if fallback:
        _active = fallback
        logger.warning(
            "sc_cid_fallback_to_settings",
            partial=fallback[:8] + "...",
        )
    else:
        logger.error("sc_cid_no_client_id_available")
    return _active


async def on_auth_failure() -> str | None:
    """Force-scrape a new client_id after SC returned 401.

    Updates both Redis and the process-local cache.
    Returns the new ID, or None when scraping fails.
    """
    global _active

    logger.warning("sc_cid_refresh_triggered_by_401")
    fresh = await _scrape()
    if not fresh:
        logger.error("sc_cid_refresh_failed_after_401")
        return None

    _active = fresh
    await _store_in_redis(fresh)
    return fresh


async def store_external(client_id: str) -> None:
    """Store a client_id obtained externally (e.g. by sc_id_refresher).

    Updates both the process-local cache and Redis so all subsequent
    SoundCloud calls in this process use the new credential immediately.
    """
    global _active

    if not client_id:
        return
    _active = client_id
    await _store_in_redis(client_id)
    logger.info(
        "sc_cid_stored_externally",
        partial=client_id[:8] + "...",
    )
