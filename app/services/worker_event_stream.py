"""Per-worker Redis Stream + per-job timeline reader.

Two parallel surfaces feed the admin "trace" UI:

- ``worker_events:{worker_id}`` — last N audit events for one
  worker (heartbeats, claims, results, anomalies, auth fails).
- ``job_trace:{job_id}`` — full timeline for one LyricsJob,
  reconstructed from ``LyricsJob.tier_attempts`` plus any matching
  ``WorkerAuditLog`` rows. Computed on demand (not streamed).

Stream events are published from `compute_worker_service._log_audit`
so every audit row also lands here. We trim with ``MAXLEN ~`` to
keep storage bounded on chatty workers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from app.core.redis import get_redis_client

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

WORKER_EVENT_STREAM_PREFIX = "worker_events:"
WORKER_EVENT_MAXLEN = 1000


def _stream_key(worker_id: str) -> str:
    return f"{WORKER_EVENT_STREAM_PREFIX}{worker_id}"


async def publish(
    worker_id: str | None,
    *,
    action: str,
    job_id: str | None = None,
    status_code: int | None = None,
    ip: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Append one audit-equivalent event to the worker stream.

    Failures are swallowed: observability must never block the
    primary request path.
    """
    if not worker_id:
        return
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "job_id": job_id or "",
        "status_code": (
            "" if status_code is None else str(status_code)
        ),
        "ip": ip or "",
        "meta": json.dumps(
            meta or {}, ensure_ascii=False, default=str
        ),
    }
    try:
        redis = get_redis_client()
        await redis.xadd(
            _stream_key(worker_id),
            payload,
            maxlen=WORKER_EVENT_MAXLEN,
            approximate=True,
        )
    except Exception:
        logger.debug(
            "worker_event_publish_failed",
            worker_id=worker_id,
            action=action,
        )


async def tail(
    worker_id: str,
    *,
    last_id: str = "$",
    count: int = 100,
    block_ms: int = 1000,
) -> tuple[str, list[dict[str, Any]]]:
    """Block until new events arrive (or timeout), return them.

    Returns ``(new_last_id, events)``. Pass ``last_id="$"`` on the
    first call to get only events that arrive after subscription.
    """
    redis = get_redis_client()
    try:
        result = await redis.xread(
            {_stream_key(worker_id): last_id},
            count=count,
            block=block_ms,
        )
    except Exception:
        return last_id, []
    if not result:
        return last_id, []
    events: list[dict[str, Any]] = []
    new_last = last_id
    for _stream, entries in result:
        for entry_id, data in entries:
            new_last = (
                entry_id
                if isinstance(entry_id, str)
                else entry_id.decode()
            )
            ev = {
                k.decode() if isinstance(k, bytes) else k: (
                    v.decode()
                    if isinstance(v, bytes)
                    else v
                )
                for k, v in data.items()
            }
            ev["id"] = new_last
            meta_raw = ev.get("meta")
            if isinstance(meta_raw, str) and meta_raw:
                try:
                    ev["meta"] = json.loads(meta_raw)
                except (TypeError, ValueError):
                    pass
            events.append(ev)
    return new_last, events


async def fetch_recent(
    worker_id: str,
    *,
    count: int = 200,
) -> list[dict[str, Any]]:
    """Snapshot the last ``count`` events without blocking."""
    redis = get_redis_client()
    try:
        rows = await redis.xrevrange(
            _stream_key(worker_id),
            count=count,
        )
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for entry_id, data in rows:
        ev = {
            k.decode() if isinstance(k, bytes) else k: (
                v.decode()
                if isinstance(v, bytes)
                else v
            )
            for k, v in data.items()
        }
        ev["id"] = (
            entry_id
            if isinstance(entry_id, str)
            else entry_id.decode()
        )
        meta_raw = ev.get("meta")
        if isinstance(meta_raw, str) and meta_raw:
            try:
                ev["meta"] = json.loads(meta_raw)
            except (TypeError, ValueError):
                pass
        out.append(ev)
    return out


__all__ = [
    "WORKER_EVENT_MAXLEN",
    "WORKER_EVENT_STREAM_PREFIX",
    "fetch_recent",
    "publish",
    "tail",
]
