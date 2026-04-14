from collections.abc import Awaitable, Callable

from starlette.middleware.base import (
    BaseHTTPMiddleware,
)
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[
            [Request], Awaitable[Response]
        ],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = (
            "nosniff"
        )
        ct = response.headers.get("content-type", "")
        if ct.startswith(
            ("audio/", "video/", "image/")
        ):
            response.headers[
                "Content-Security-Policy"
            ] = "default-src 'none'"
        return response
