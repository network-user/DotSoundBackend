"""Send-and-wait client for SoundCloud RPC over the ComputeJob queue.

A backend caller enqueues a ``soundcloud_rpc`` ComputeJob, the
remote ComputeWorker claims it (HMAC pull protocol), executes the
actual SoundCloud HTTP call from its own egress IP, and posts the
result back. The result router mirrors the envelope into Redis
under ``sc_rpc_result:{request_id}``; this client waits for it
with a bounded timeout and falls back to a local execution path
when the offload framework is disabled or the worker is offline.

Two flags govern routing (read from :mod:`app.config`):

* ``sc_offload_enabled`` -- master switch. ``False`` keeps every
  call on the synchronous local path. Default ``False`` so this
  change ships dormant; flip to ``True`` after the worker is up.
* ``sc_offload_wait_seconds`` -- maximum time to wait for the
  envelope before declaring the worker unreachable and falling
  back. Keep small (~30 s) so a stuck worker does not stall the
  whole Taskiq slot.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from dotsound_private_core.contracts.sc_rpc_protocol import (
    SoundCloudRpcMethod,
    is_retryable_error,
    is_terminal_error,
)

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.services import compute_queue_service as q

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ScRpcOffloadDisabled(Exception):
    """Raised when caller asked for offload but the flag is off."""


class ScRpcUnreachable(Exception):
    """The worker did not respond within the configured timeout."""


class ScRpcUpstreamError(Exception):
    """Worker reported an error envelope. ``error_kind`` is populated
    from :class:`SoundCloudRpcErrorKind`."""

    def __init__(
        self,
        *,
        error_kind: str,
        error_message: str,
        upstream_status: int,
    ) -> None:
        super().__init__(f"sc_rpc_error[{error_kind}] {error_message[:200]}")
        self.error_kind = error_kind
        self.error_message = error_message
        self.upstream_status = upstream_status


def offload_enabled() -> bool:
    return bool(getattr(settings, "sc_offload_enabled", False))


def _wait_timeout() -> float:
    return float(getattr(settings, "sc_offload_wait_seconds", 30.0))


async def _wait_for_envelope(
    request_id: str,
    *,
    timeout_seconds: float,
) -> dict[str, Any] | None:
    """Poll Redis for the RPC result envelope.

    Uses short adaptive sleeps (250ms initially, doubling up to 2s)
    so a fast worker round-trip returns in < 1s while a slow one
    does not pile up Redis ``GET`` calls.
    """
    redis = get_redis_client()
    key = f"sc_rpc_result:{request_id}"
    deadline = asyncio.get_running_loop().time() + max(1.0, timeout_seconds)
    delay = 0.25
    while True:
        try:
            raw = await redis.get(key)
        except Exception as exc:
            logger.warning(
                "sc_rpc_wait_redis_failed",
                request_id=request_id,
                error=str(exc)[:200],
            )
            return None
        if raw:
            try:
                blob = json.loads(raw)
            except (TypeError, ValueError):
                return None
            envelope = blob.get("envelope") if isinstance(blob, dict) else None
            if isinstance(envelope, dict):
                return envelope
            return None
        if asyncio.get_running_loop().time() >= deadline:
            return None
        await asyncio.sleep(delay)
        delay = min(2.0, delay * 2)


async def call_soundcloud_rpc(
    method: SoundCloudRpcMethod | str,
    *,
    args: dict[str, Any] | None = None,
    sticky_key: str = "",
    request_id: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Send a SoundCloud RPC to the worker and return ``data``.

    Raises:
        ScRpcOffloadDisabled: caller forgot to gate on
            :func:`offload_enabled`.
        ScRpcUnreachable: the worker did not produce an envelope
            in time; the caller should drop to its local path.
        ScRpcUpstreamError: the worker returned a classified
            upstream error (dead track, rate limit, etc.). The
            caller decides whether to retry / fall back.
    """
    if not offload_enabled():
        raise ScRpcOffloadDisabled

    method_str = (
        method.value if isinstance(method, SoundCloudRpcMethod) else method
    )

    async with AsyncSessionLocal() as session:
        job = await q.enqueue_soundcloud_rpc(
            session,
            method=method_str,
            args=args or {},
            sticky_key=sticky_key,
            request_id=request_id,
            timeout_seconds=float(timeout_seconds or 25.0),
        )
        await session.commit()
        rid = job.target_id or job.id

    envelope = await _wait_for_envelope(
        rid,
        timeout_seconds=float(
            timeout_seconds if timeout_seconds is not None else _wait_timeout()
        ),
    )
    if envelope is None:
        logger.warning(
            "sc_rpc_offload_unreachable",
            request_id=rid,
            method=method_str,
        )
        raise ScRpcUnreachable

    success = bool(envelope.get("success"))
    if success:
        data = envelope.get("data")
        return data if isinstance(data, dict) else {"data": data}

    error_kind = str(envelope.get("error_kind") or "unknown")
    error_message = str(envelope.get("error_message") or "")
    upstream_status = int(envelope.get("upstream_status") or 0)
    logger.info(
        "sc_rpc_offload_error",
        request_id=rid,
        method=method_str,
        error_kind=error_kind,
        upstream_status=upstream_status,
        terminal=is_terminal_error(error_kind),
        retryable=is_retryable_error(error_kind),
    )
    raise ScRpcUpstreamError(
        error_kind=error_kind,
        error_message=error_message,
        upstream_status=upstream_status,
    )


__all__ = [
    "ScRpcOffloadDisabled",
    "ScRpcUnreachable",
    "ScRpcUpstreamError",
    "call_soundcloud_rpc",
    "offload_enabled",
]
