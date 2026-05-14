"""CSRF double-submit defense.

The auth flow stores the access token in an ``httpOnly`` cookie
(``ds_access``); to keep mutating cross-site requests from riding
that cookie we also issue a non-``httpOnly`` cookie (``ds_csrf``)
which the SPA must echo back in the ``X-CSRF-Token`` header on every
mutating call. Both must match.

GET/HEAD/OPTIONS/TRACE bypass the check. The middleware exempts a
narrow set of paths that never carry session cookies (Telegram
WebApp login, internal pull-worker API gated by HMAC, admin auth
init, webhook endpoints) so existing automation does not break.

Requests that explicitly carry ``Authorization: Bearer ...`` also
bypass the check. The classic CSRF threat model is "browser silently
rides an ambient session cookie from another origin"; an explicit
``Authorization`` header cannot be forged that way (the CORS
preflight blocks it), so a Bearer-authenticated request is by
construction not a CSRF. This is required for the Telegram Mini App
webview on iOS/Android where the ``ds_csrf`` cookie does not always
survive round-tripping through ``document.cookie``.
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

CSRF_COOKIE_NAME = "ds_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

# Paths that bypass the CSRF check entirely. These either authenticate
# via a different mechanism (HMAC, Telegram-signed initData, admin
# bootstrap), or simply do not accept session cookies.
_EXEMPT_PREFIXES = (
    "/api/v1/auth/telegram",
    "/api/v1/auth/verify-code",
    "/api/v1/auth/" + "generate-code",
    "/api/v1/auth/email/request",
    "/api/v1/auth/email/verify",
    "/api/v1/internal/",
    "/api/v1/admin/auth/",
    "/internal/",
    "/health",
)


def _is_exempt(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        method = request.method.upper()

        if method in _SAFE_METHODS or _is_exempt(path):
            response = await call_next(request)
            self._ensure_cookie(request, response)
            return response

        # Only enforce CSRF when the request actually authenticates via
        # the session cookie. Bearer-token clients (Telegram Mini App
        # webview, mobile clients with flaky cookie jars, CI smoke
        # probes) are unaffected: a cross-site attacker cannot forge
        # an ``Authorization`` header (the CORS preflight blocks it),
        # so the cookie-ride attack model that CSRF defends against
        # does not apply. We therefore bypass the check whenever the
        # caller proves possession of the token explicitly.
        auth_header = request.headers.get("authorization", "")
        has_bearer_auth = auth_header.lower().startswith("bearer ")
        has_cookie_auth = bool(request.cookies.get("ds_access"))
        if has_bearer_auth or not has_cookie_auth:
            response = await call_next(request)
            self._ensure_cookie(request, response)
            return response

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "")
        header_token = request.headers.get(CSRF_HEADER_NAME, "")
        if (
            not cookie_token
            or not header_token
            or not secrets.compare_digest(cookie_token, header_token)
        ):
            logger.warning(
                "csrf_check_failed",
                path=path,
                cookie_present=bool(cookie_token),
                header_present=bool(header_token),
            )
            return JSONResponse(
                {"detail": "CSRF token missing or invalid"},
                status_code=403,
            )

        response = await call_next(request)
        self._ensure_cookie(request, response)
        return response

    def _ensure_cookie(self, request: Request, response: Response) -> None:
        if request.cookies.get(CSRF_COOKIE_NAME):
            return
        token = secrets.token_urlsafe(32)
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=token,
            max_age=settings.jwt_expire_days * 24 * 3600,
            httponly=False,  # SPA must read it
            secure=not settings.debug,
            samesite="lax",
            path="/",
        )
