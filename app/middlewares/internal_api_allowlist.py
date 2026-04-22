"""IP allowlist enforcement for /api/v1/internal/* endpoints.

Belongs to the perimeter defense layer (see plan §10.3). Decision
function `is_ip_in_cidrs` lives in PrivateCore; here we only do
transport: read settings, look at request, return 404 to stay
silent for scanners.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from dotsound_private_core.services.network_policy import (
    is_ip_in_cidrs,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

_INTERNAL_PREFIX = "/api/v1/internal/"


class InternalApiAllowlistMiddleware(BaseHTTPMiddleware):
    """Block any request to /api/v1/internal/* whose source IP is
    not in `settings.internal_api_allowed_cidrs_list`.

    Returns 404 Not Found rather than 403 Forbidden so that
    scanners cannot enumerate the existence of the internal API.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[
            [Request], Awaitable[Response]
        ],
    ) -> Response:
        if not request.url.path.startswith(
            _INTERNAL_PREFIX
        ):
            return await call_next(request)

        client_ip = (
            request.client.host
            if request.client
            else None
        )
        cidrs = settings.internal_api_allowed_cidrs_list
        if not is_ip_in_cidrs(client_ip, cidrs):
            logger.warning(
                "internal_api_ip_blocked",
                ip=client_ip,
                path=request.url.path,
                method=request.method,
            )
            return JSONResponse(
                status_code=404,
                content={"detail": "Not Found"},
            )

        return await call_next(request)
