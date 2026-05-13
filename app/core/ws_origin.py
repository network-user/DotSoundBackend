"""WebSocket Origin allowlist.

Browsers send the ``Origin`` header on the WS upgrade request; non-browser
clients omit it. We require the Origin (when present) to be in the same
allowlist as CORS. Same-origin handshakes (no Origin header at all) are
permitted so headless clients keep working.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import structlog
from fastapi import WebSocket

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _normalize(origin: str) -> str:
    parts = urlsplit(origin)
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}".lower().rstrip("/")


def is_origin_allowed(origin: str | None) -> bool:
    if origin is None:
        return True
    o = _normalize(origin)
    if not o:
        return False
    if settings.debug:
        return True
    allowed = {
        _normalize(o)
        for o in settings.allowed_origins_list
        if o and o != "*"
    }
    return o in allowed


async def reject_if_bad_origin(websocket: WebSocket) -> bool:
    """Return True if the connection was rejected; caller should ``return``."""
    origin = websocket.headers.get("origin")
    if is_origin_allowed(origin):
        return False
    logger.warning("ws_origin_rejected", origin=origin)
    await websocket.close(code=4403)
    return True
