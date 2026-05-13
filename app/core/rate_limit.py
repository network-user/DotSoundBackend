from ipaddress import ip_address, ip_network

from slowapi import Limiter
from starlette.requests import Request

from app.config import settings


def _trusted_networks() -> list:
    nets = []
    for cidr in settings.trusted_proxy_cidrs_list:
        try:
            nets.append(ip_network(cidr, strict=False))
        except ValueError:
            continue
    return nets


_TRUSTED = _trusted_networks()


def _real_client_ip(request: Request) -> str:
    """Resolve the originating client IP behind any number of trusted proxies.

    Walks ``X-Forwarded-For`` right-to-left, peeling off addresses that
    belong to a trusted-proxy CIDR. The first untrusted address is the
    real client. Untrusted ``X-Forwarded-For`` is ignored — falls back
    to the direct peer.
    """
    peer = (
        request.client.host
        if request.client
        else "0.0.0.0"
    )
    if not _TRUSTED:
        return peer
    try:
        peer_ip = ip_address(peer)
    except ValueError:
        return peer
    if not any(peer_ip in net for net in _TRUSTED):
        return peer
    xff = request.headers.get("x-forwarded-for", "")
    if not xff:
        return peer
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    for raw in reversed(parts):
        try:
            candidate = ip_address(raw)
        except ValueError:
            continue
        if any(candidate in net for net in _TRUSTED):
            continue
        return str(candidate)
    return peer


limiter = Limiter(
    key_func=_real_client_ip,
    default_limits=["200/minute"],
    storage_uri=settings.redis_url,
)
