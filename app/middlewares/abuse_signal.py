"""Lightweight middleware that captures the X-DS-Signal header.

The frontend sends an opaque token in this header *only after*
the user accepted the cookie/consent banner (see
``frontend/src/components/Legal/ConsentBanner.tsx``). Without
consent the header is absent and we do nothing -- backend's
existing IP-based rate-limit still applies.

The token never carries raw fingerprint bytes; it is a short
HMAC of normalized client signals (canvas-class hash, webgl
vendor class, timezone, UA class). Backend stores only the
token itself, scoped to a short TTL window.
"""

from __future__ import annotations

import structlog
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class AbuseSignalMiddleware(BaseHTTPMiddleware):
    """Stash the opaque client-signal token on ``request.state``.

    Downstream services (login, register, upload) read
    ``request.state.abuse_signal`` and combine it with their
    own counts before calling ``AbuseSignalService.evaluate_event``.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        token = request.headers.get("X-DS-Signal")
        if token:
            request.state.abuse_signal = token.strip()[:64]
        else:
            request.state.abuse_signal = None
        return await call_next(request)
