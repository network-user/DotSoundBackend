import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

_SKIP_PATHS = frozenset(
    {"/api/v1/health", "/docs", "/openapi.json"}
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[
            [Request], Awaitable[Response]
        ],
    ) -> Response:
        request_id = str(uuid.uuid4())[:12]
        client_ip = (
            request.client.host
            if request.client
            else "unknown"
        )

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
        )

        skip = request.url.path in _SKIP_PATHS
        start = time.perf_counter()

        if not skip:
            logger.info("http_request_started")

        response = await call_next(request)

        duration_ms = round(
            (time.perf_counter() - start) * 1000, 2
        )

        response.headers["X-Request-ID"] = request_id

        if not skip:
            logger.info(
                "http_request_completed",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

        structlog.contextvars.clear_contextvars()
        return response
