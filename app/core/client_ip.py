from __future__ import annotations

from collections.abc import Sequence

from dotsound_private_core.services.network_policy import is_ip_in_cidrs
from starlette.requests import Request

from app.config import settings


def resolve_forwarded_client_ip(
    peer_ip: str | None,
    x_forwarded_for: str | None,
    trusted_proxy_cidrs: Sequence[str],
) -> str | None:
    if not peer_ip:
        return None
    if not trusted_proxy_cidrs or not is_ip_in_cidrs(
        peer_ip, trusted_proxy_cidrs
    ):
        return peer_ip
    if not x_forwarded_for:
        return peer_ip

    parts = [
        part.strip() for part in x_forwarded_for.split(",") if part.strip()
    ]
    for candidate in reversed(parts):
        if is_ip_in_cidrs(candidate, trusted_proxy_cidrs):
            continue
        return candidate
    return peer_ip


def resolve_request_client_ip(
    request: Request,
    trusted_proxy_cidrs: Sequence[str],
) -> tuple[str | None, str | None]:
    peer_ip = request.client.host if request.client else None
    client_ip = resolve_forwarded_client_ip(
        peer_ip,
        request.headers.get("x-forwarded-for"),
        trusted_proxy_cidrs,
    )
    return client_ip, peer_ip


def internal_api_trusted_proxy_cidrs() -> list[str]:
    return settings.internal_api_trusted_proxies_effective_list
