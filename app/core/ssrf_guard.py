"""URL allowlist / SSRF guard for user-supplied URLs.

Used on import endpoints (YouTube/SoundCloud/Bandcamp/Yandex/VK) and
anywhere user input flows into a server-side ``GET``. Rejects:

* non ``http(s)`` schemes (``file://``, ``gopher://``, ``data:`` …)
* metadata endpoints (169.254.169.254 + cloud variants)
* RFC 1918 / loopback / link-local / multicast / reserved IPs
* hostnames that resolve to any of the above
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from fastapi import HTTPException, status

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_METADATA_HOSTS = frozenset(
    {
        "169.254.169.254",
        "fd00:ec2::254",
        "metadata.google.internal",
        "metadata.azure.com",
    }
)


def _is_private(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolves_to_private(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # Refuse on DNS failure: do not let attackers exploit
        # short-lived resolver flaps to bypass the check.
        return True
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        if _is_private(sockaddr[0]):
            return True
    return False


def assert_public_http_url(url: str, *, field: str = "url") -> None:
    parts = urlsplit(url)
    scheme = (parts.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field}: unsupported scheme {scheme!r}",
        )
    host = (parts.hostname or "").strip().lower()
    if not host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field}: missing host",
        )
    if host in _METADATA_HOSTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field}: blocked host",
        )
    if _is_private(host):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field}: private/loopback address blocked",
        )
    if _resolves_to_private(host):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field}: host resolves to private network",
        )
