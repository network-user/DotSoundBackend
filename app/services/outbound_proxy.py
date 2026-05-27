from __future__ import annotations

import threading
import time
from typing import Any, Protocol
from urllib.parse import SplitResult, urlsplit, urlunsplit

import httpx
import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_lock = threading.Lock()
_static_rr: int = 0
_STARTED_AT_EXT = "dotsound_outbound_started_at"


class _OutboundMetrics(Protocol):
    def record_request(self, service: str) -> None: ...

    def record_response(self, service: str, status_code: int) -> None: ...

    def record_transport_error(self, service: str) -> None: ...

    def record_request_event(
        self,
        service: str,
        *,
        method: str,
        url: str,
        identity: str | None,
        transport: str,
        egress_ip: str | None = None,
        status_code: int | None = None,
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> None: ...


def proxy_url_for_httpx(proxy_url: str | None) -> str | None:
    """Normalize proxy URLs for httpx (socksio rejects ``socks5h://``)."""
    if not proxy_url:
        return None
    parsed = urlsplit(proxy_url)
    if parsed.scheme != "socks5h":
        return proxy_url
    return urlunsplit(
        (
            "socks5",
            parsed.netloc,
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


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


def instrument_httpx_client_kwargs(
    client_kwargs: dict[str, Any],
    *,
    service: str,
    proxy_url: str | None,
) -> None:
    hooks = dict(client_kwargs.get("event_hooks") or {})
    request_hooks = list(hooks.get("request") or [])
    response_hooks = list(hooks.get("response") or [])

    async def on_request(request: httpx.Request) -> None:
        request.extensions[_STARTED_AT_EXT] = time.monotonic()
        metrics = _private_metrics()
        if metrics is not None:
            metrics.record_request(service)

    async def on_response(response: httpx.Response) -> None:
        started = response.request.extensions.get(_STARTED_AT_EXT)
        duration_ms = None
        if isinstance(started, float):
            duration_ms = (time.monotonic() - started) * 1000
        _record_request_event(
            service=service,
            method=response.request.method,
            url=str(response.request.url),
            proxy_url=proxy_url,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

    request_hooks.append(on_request)
    response_hooks.append(on_response)
    hooks["request"] = request_hooks
    hooks["response"] = response_hooks
    client_kwargs["event_hooks"] = hooks


def record_outbound_proxy_error(
    *,
    service: str,
    proxy_url: str | None,
    method: str,
    url: str,
    error: BaseException,
    started_at: float | None = None,
) -> None:
    duration_ms = None
    if started_at is not None:
        duration_ms = (time.monotonic() - started_at) * 1000
    metrics = _private_metrics()
    if metrics is not None:
        metrics.record_transport_error(service)
    _record_request_event(
        service=service,
        method=method,
        url=url,
        proxy_url=proxy_url,
        duration_ms=duration_ms,
        error=str(error),
    )


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


def _private_metrics() -> _OutboundMetrics | None:
    try:
        from dotsound_private_core.services.outbound import metrics
    except Exception:
        return None
    return metrics


def _record_request_event(
    *,
    service: str,
    method: str,
    url: str,
    proxy_url: str | None,
    status_code: int | None = None,
    duration_ms: float | None = None,
    error: str | None = None,
) -> None:
    metrics = _private_metrics()
    if metrics is None:
        return
    if status_code is not None:
        metrics.record_response(service, status_code)
    transport, identity, egress_ip = _transport_metadata(proxy_url)
    metrics.record_request_event(
        service,
        method=method,
        url=url,
        identity=identity,
        transport=transport,
        egress_ip=egress_ip,
        status_code=status_code,
        duration_ms=duration_ms,
        error=error,
    )


def _transport_metadata(
    proxy_url: str | None,
) -> tuple[str, str | None, str | None]:
    if not proxy_url:
        return "direct", None, None
    if _is_tor_proxy(proxy_url):
        from app.services.tor_pool import get_tor_pool

        pool = get_tor_pool()
        if pool is not None:
            desc = pool.describe_proxy(proxy_url)
            if desc is not None:
                return (
                    "tor",
                    str(desc.get("identity") or ""),
                    _non_empty_str(desc.get("egress_ip")),
                )
        parsed = urlsplit(proxy_url)
        return "tor", _proxy_identity("tor", parsed), None
    parsed = urlsplit(proxy_url)
    return "proxy", _proxy_identity("proxy", parsed), parsed.hostname


def _is_tor_proxy(proxy_url: str) -> bool:
    parsed = urlsplit(proxy_url)
    return parsed.scheme in {"socks5", "socks5h"} and parsed.hostname in {
        "127.0.0.1",
        "localhost",
    }


def _proxy_identity(prefix: str, parsed: SplitResult) -> str:
    host = parsed.hostname or "unknown"
    if parsed.port is None:
        return f"{prefix}:{host}"
    return f"{prefix}:{host}:{parsed.port}"


def _non_empty_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
