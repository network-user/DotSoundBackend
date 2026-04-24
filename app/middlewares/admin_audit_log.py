"""Best-effort audit log for mutating admin API calls."""

from __future__ import annotations

import structlog
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

from app.core.auth import AuthError, decode_admin_token
from app.core.db import AsyncSessionLocal
from app.middlewares.admin_security import (
    ADMIN_AUTH_PATH_PREFIX,
)
from app.repositories.admin_action_log import (
    AdminActionLogRepository,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_ADMIN_API_PREFIX = "/api/v1/admin"
_MUTATING = frozenset(
    {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }
)


def _bearer(request: Request) -> str | None:
    value = (request.headers.get("authorization") or "").strip()
    if not value.lower().startswith("bearer "):
        return None
    return value[7:].strip() or None


def _client_ip(request: Request) -> str | None:
    if request.client is not None and request.client.host is not None:
        return request.client.host
    return None


class AdminAuditLogMiddleware(BaseHTTPMiddleware):
    """Log mutating /api/v1/admin requests to ``admin_action_log``."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        path = request.url.path
        if request.method not in _MUTATING:
            return response
        if not path.startswith(
            _ADMIN_API_PREFIX
        ) or path.startswith(
            f"{ADMIN_AUTH_PATH_PREFIX}/"
        ):
            return response
        if path.startswith(
            f"{_ADMIN_API_PREFIX}/ws"
        ) or path == f"{_ADMIN_API_PREFIX}/ws":
            return response
        token = _bearer(request)
        if not token:
            return response
        try:
            payload = decode_admin_token(token)
        except AuthError:
            return response
        try:
            user_id = int(str(payload.get("sub", "0")))
        except (TypeError, ValueError):
            return response
        if user_id < 1:
            return response

        action = f"{request.method} {path}"
        if request.url.query:
            q = request.url.query
            if len(q) > 512:
                q = f"{q[:512]}…"
            action = f"{action}?{q}"

        meta: dict[object, object] = {
            "status_code": response.status_code,
        }
        client_ip = _client_ip(request)
        try:
            async with AsyncSessionLocal() as session:
                try:
                    repo = AdminActionLogRepository(session)
                    await repo.write(
                        user_id=user_id,
                        action=action,
                        target_type="http",
                        target_id=request.method,
                        ip=client_ip,
                        meta=meta,
                    )
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
        except Exception:  # noqa: BLE001
            logger.exception(
                "admin_audit_log_write_failed",
                path=path,
                user_id=user_id,
            )
        return response
