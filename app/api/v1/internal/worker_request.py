from __future__ import annotations

import structlog
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client_ip import (
    internal_api_trusted_proxy_cidrs,
    resolve_request_client_ip,
)
from app.models.compute_worker import ComputeWorker
from app.services import compute_worker_service as cws

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def client_ip(request: Request) -> str | None:
    resolved = getattr(
        request.state,
        "internal_api_client_ip",
        None,
    )
    if isinstance(resolved, str) and resolved:
        return resolved
    client, _peer = resolve_request_client_ip(
        request,
        internal_api_trusted_proxy_cidrs(),
    )
    return client


async def verify_worker_hmac_request(
    request: Request,
    session: AsyncSession,
) -> tuple[ComputeWorker, bytes]:
    body = await request.body()
    try:
        worker = await cws.verify_worker_request(
            session,
            worker_id=request.headers.get("X-Worker-Id", ""),
            timestamp=request.headers.get("X-Timestamp", ""),
            nonce=request.headers.get("X-Nonce", ""),
            signature_hex=request.headers.get("X-Worker-Signature", ""),
            method=request.method,
            path=request.url.path,
            body=body,
            client_ip=client_ip(request),
            signature_version=request.headers.get(
                "X-Worker-Signature-Version"
            ),
        )
    except cws.WorkerNotFoundError:
        await cws._log_audit(
            session,
            worker_id=request.headers.get("X-Worker-Id"),
            ip=client_ip(request),
            action="auth_fail",
            status_code=404,
        )
        await session.commit()
        raise HTTPException(status_code=404) from None
    except cws.WorkerAuthError as exc:
        await cws._log_audit(
            session,
            worker_id=request.headers.get("X-Worker-Id"),
            ip=client_ip(request),
            action="auth_fail",
            status_code=401,
            meta={"reason": str(exc)},
        )
        await session.commit()
        raise HTTPException(status_code=401) from exc

    return worker, body


__all__ = ["client_ip", "verify_worker_hmac_request"]
