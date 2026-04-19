from __future__ import annotations

import hmac
import secrets
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import (
    BaseHTTPMiddleware,
)
from starlette.requests import Request
from starlette.responses import (
    JSONResponse,
    Response,
)

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

ADMIN_PATH_PREFIX = "/api/v1/admin"
ADMIN_AUTH_PATH_PREFIX = "/api/v1/admin/auth"
CSRF_COOKIE_NAME = "admin_csrf"
CSRF_HEADER_NAME = "X-Admin-CSRF"
ADMIN_STEP_UP_HEADER = "X-Admin-Step-Up"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

CSRF_EXEMPT_PATHS = frozenset(
    {
        f"{ADMIN_AUTH_PATH_PREFIX}/csrf",
        f"{ADMIN_AUTH_PATH_PREFIX}/login",
        f"{ADMIN_AUTH_PATH_PREFIX}/init/start",
        f"{ADMIN_AUTH_PATH_PREFIX}/init/confirm",
        f"{ADMIN_AUTH_PATH_PREFIX}/refresh",
        f"{ADMIN_AUTH_PATH_PREFIX}/devices/confirm",
        f"{ADMIN_AUTH_PATH_PREFIX}/devices/request-approval",
    }
)


def _csp_value() -> str:
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'self' "
        "ws: wss:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )


def _generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _set_csrf_cookie(response: Response, value: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=value,
        max_age=60 * 60 * 12,
        httponly=False,
        secure=not settings.debug,
        samesite="strict",
        path="/api/v1/admin",
    )


def _is_csrf_exempt(path: str) -> bool:
    return path in CSRF_EXEMPT_PATHS


class AdminSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if not path.startswith(ADMIN_PATH_PREFIX):
            return await call_next(request)

        method = request.method.upper()
        has_admin_csrf_cookie = bool(request.cookies.get(CSRF_COOKIE_NAME))
        is_bearer_request = bool(
            request.headers.get("authorization", "")
            .lower()
            .startswith("bearer ")
        )
        if (
            method not in SAFE_METHODS
            and not _is_csrf_exempt(path)
            and has_admin_csrf_cookie
            and not is_bearer_request
        ):
            cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "")
            header_token = request.headers.get(CSRF_HEADER_NAME, "")
            if (
                not cookie_token
                or not header_token
                or not hmac.compare_digest(cookie_token, header_token)
            ):
                logger.warning(
                    "admin_csrf_failed",
                    path=path,
                    method=method,
                )
                return JSONResponse(
                    status_code=403,
                    content={"detail": ("CSRF token missing " "or invalid")},
                )

        response = await call_next(request)
        existing_csrf = request.cookies.get(CSRF_COOKIE_NAME)
        if not existing_csrf and not is_bearer_request:
            new_token = _generate_csrf_token()
            _set_csrf_cookie(response, new_token)

        response.headers["Content-Security-Policy"] = _csp_value()
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        if not settings.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; " "includeSubDomains; preload"
            )
        return response
