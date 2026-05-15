from __future__ import annotations

import threading

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_lock = threading.Lock()
_static_rr: int = 0


def get_outbound_proxy(service: str = "") -> str | None:
    """Tor SOCKS5 or static HTTP(S)/SOCKS URL, round-robin per pool."""
    from app.config import settings

    urls = settings.outbound_static_proxy_urls_list
    if urls:
        return _static_proxy_url(urls, service)
    from app.services.tor_pool import get_tor_pool

    pool = get_tor_pool()
    if pool is None:
        return None
    return pool.get_proxy(service)


def outbound_proxy_configured() -> bool:
    from app.config import settings

    if settings.outbound_static_proxy_urls_list:
        return True
    from app.services.tor_pool import get_tor_pool

    return get_tor_pool() is not None


def report_outbound_proxy_result(proxy_url: str | None, *, ok: bool) -> None:
    if not proxy_url:
        return
    from app.services.tor_pool import get_tor_pool

    pool = get_tor_pool()
    if pool is None:
        return
    pool.report_proxy_result(proxy_url, ok=ok)


def _static_proxy_url(urls: list[str], service: str) -> str:
    global _static_rr
    with _lock:
        idx = _static_rr % len(urls)
        _static_rr += 1
        chosen = urls[idx]
    logger.info(
        "outbound_static_proxy_selected",
        pool_index=idx,
        pool_size=len(urls),
        service=service,
    )
    return chosen
