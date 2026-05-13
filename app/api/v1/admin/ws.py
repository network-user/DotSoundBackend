"""Admin WebSocket endpoint for live updates.

Multiplexes channels over a single connection:

- ``overview`` — KPI snapshot every 5 s.
- ``containers`` — Docker container summary every 5 s.
- ``logs`` — live tail of recent backend log entries via Loki
  (selectors are passed in the subscribe message).
- ``tasks_progress`` — live updates on ``lyrics_jobs`` rows in
  flight (queued/running/finished).
- ``alerts`` — server-pushed admin alerts (mirrors what
  ``admin_alert_service`` sends to Telegram).

Auth uses an admin JWT in the ``Sec-WebSocket-Protocol`` header
(or ``token`` query param fallback). The token is validated through
the same machinery as HTTP requests, including session-active and
device-trusted checks.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from datetime import UTC
from typing import Any

import structlog
from dotsound_private_core.services.admin_security_policy import (
    ADMIN_SESSION_TTL_SECONDS,
)
from fastapi import APIRouter, Query, WebSocket
from fastapi import status as ws_status
from starlette.websockets import WebSocketDisconnect, WebSocketState

from app.config import settings
from app.core.auth import (
    AuthError,
    decode_admin_token,
)
from app.core.db import AsyncSessionLocal
from app.core.ws_origin import reject_if_bad_origin
from app.core.observability import (
    ws_gauge_dec,
    ws_gauge_inc,
)
from app.core.redis import get_redis_client
from app.repositories.admin_device import (
    AdminDeviceRepository,
)
from app.repositories.admin_session import (
    AdminSessionRepository,
)
from app.repositories.lyrics_job import LyricsJobRepository
from app.services.admin_dashboard_service import (
    collect_overview,
)
from app.services.container_health_service import (
    get_container_summary,
)
from app.services.local_dev_log_service import (
    is_local_dev_logs_enabled,
    query_dev_logs,
)
from app.services.loki_service import (
    LokiServiceError,
    query_range,
)

router = APIRouter(prefix="/ws", tags=["admin-ws"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

ALLOWED_CHANNELS: frozenset[str] = frozenset(
    {
        "overview",
        "containers",
        "logs",
        "tasks_progress",
        "alerts",
        "worker_logs",
        "job_trace",
    }
)

_WS_LIMIT_KEY_PREFIX = "admin:ws:conn:"
_WS_LIMIT_TTL_SECONDS = 60 * 60 * 2
_WS_MAX_CONN_PER_USER = 5


async def _acquire_ws_slot(user_id: int) -> bool:
    """Atomically claim a per-user WS connection slot in Redis.

    Returns ``False`` when the user already holds the configured
    maximum concurrent connections. The counter has a safety TTL so
    a crashed process cannot leak slots indefinitely.
    """
    redis = get_redis_client()
    key = f"{_WS_LIMIT_KEY_PREFIX}{user_id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, _WS_LIMIT_TTL_SECONDS)
    if count > _WS_MAX_CONN_PER_USER:
        await redis.decr(key)
        return False
    return True


async def _release_ws_slot(user_id: int) -> None:
    redis = get_redis_client()
    key = f"{_WS_LIMIT_KEY_PREFIX}{user_id}"
    try:
        value = await redis.decr(key)
    except Exception:
        return
    if value is not None and value <= 0:
        with contextlib.suppress(Exception):
            await redis.delete(key)


async def _authenticate(
    raw_token: str,
) -> tuple[int, int] | None:
    if not raw_token:
        return None
    try:
        payload = decode_admin_token(raw_token)
    except AuthError:
        return None
    if payload.get("scope") != "admin":
        return None
    jti = str(payload.get("jti", ""))
    user_id = int(str(payload.get("sub", "0")))
    if not jti or user_id <= 0:
        return None
    async with AsyncSessionLocal() as session:
        sessions = AdminSessionRepository(session)
        row = await sessions.get_by_jti(jti)
        if row is None or row.revoked_at is not None:
            return None
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at.timestamp() < time.time():
            return None
        devices = AdminDeviceRepository(session)
        device = await devices.get_by_id(row.device_id)
        if (
            device is None
            or device.revoked_at is not None
            or device.trusted_at is None
        ):
            return None
        return user_id, row.device_id


async def _push_overview(
    websocket: WebSocket,
) -> None:
    async with AsyncSessionLocal() as session:
        payload = await collect_overview(session)
    await websocket.send_text(
        json.dumps({"channel": "overview", "data": payload})
    )


async def _push_containers(
    websocket: WebSocket,
) -> None:
    snapshot = await get_container_summary()
    await websocket.send_text(
        json.dumps(
            {
                "channel": "containers",
                "data": snapshot,
            }
        )
    )


async def _push_tasks_progress(
    websocket: WebSocket,
    *,
    last_seen_id: list[str],
) -> None:
    async with AsyncSessionLocal() as session:
        rows = await LyricsJobRepository(session).list_recent(
            statuses=("queued", "running", "error", "done"),
            limit=40,
        )
    items = [
        {
            "id": row.id,
            "track_id": row.track_id,
            "status": row.status,
            "profile": row.profile,
            "attempts": row.attempts,
            "duration_ms": row.duration_ms,
            "updated_at": (
                row.updated_at.isoformat() if row.updated_at else None
            ),
        }
        for row in rows
    ]
    if items and items[0]["id"] == last_seen_id[0]:
        return
    if items:
        last_seen_id[0] = str(items[0]["id"])
    await websocket.send_text(
        json.dumps(
            {
                "channel": "tasks_progress",
                "data": {"items": items},
            }
        )
    )


async def _push_logs(
    websocket: WebSocket,
    *,
    selectors: dict[str, str],
    contains: str | None,
    since_ns: list[int],
) -> None:
    end_ns = int(time.time() * 1_000_000_000)
    start_ns = max(
        since_ns[0],
        end_ns - 60 * 1_000_000_000,
    )
    loki_configured = bool((settings.loki_url or "").strip())
    s = dict(selectors)
    if (
        not loki_configured
        and is_local_dev_logs_enabled()
        and s.get("service") == "dotsound-backend"
        and not s.get("container")
    ):
        s.pop("service", None)

    rows: list[dict[str, Any]] = []
    if loki_configured:
        try:
            rows = await query_range(
                selectors=selectors,
                contains=contains,
                start_ns=start_ns,
                end_ns=end_ns,
                limit=200,
            )
        except LokiServiceError as exc:
            await websocket.send_text(
                json.dumps(
                    {
                        "channel": "logs",
                        "data": {"error": str(exc)},
                    }
                )
            )
            return
    elif is_local_dev_logs_enabled():
        try:
            rows = await asyncio.to_thread(
                lambda: query_dev_logs(
                    selectors=s,
                    contains=contains,
                    start_ns=start_ns,
                    end_ns=end_ns,
                    limit=200,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            await websocket.send_text(
                json.dumps(
                    {
                        "channel": "logs",
                        "data": {"error": str(exc)},
                    }
                )
            )
            return
    else:
        return
    if not rows:
        return
    since_ns[0] = max(row.get("ts_ns", 0) for row in rows) + 1
    await websocket.send_text(
        json.dumps(
            {
                "channel": "logs",
                "data": {"items": rows},
            }
        )
    )


def _parse_log_subscribe(
    msg: dict[str, Any],
) -> tuple[dict[str, str], str | None]:
    raw = msg.get("filters", {})
    if not isinstance(raw, dict):
        raw = {}
    selectors: dict[str, str] = {}
    for key in (
        "service",
        "container",
        "level",
    ):
        value = raw.get(key)
        if value:
            selectors[key] = str(value)[:64]
    if not selectors:
        selectors["service"] = "dotsound-backend"
    contains = raw.get("contains")
    contains_clean = (
        str(contains)[:128] if isinstance(contains, str) and contains else None
    )
    return selectors, contains_clean


async def _push_worker_logs(
    websocket: WebSocket,
    *,
    worker_id: str,
    last_id: list[str],
) -> None:
    from app.services.worker_event_stream import tail

    new_last, events = await tail(
        worker_id,
        last_id=last_id[0] or "$",
        count=100,
        block_ms=200,
    )
    if not events:
        return
    last_id[0] = new_last
    await websocket.send_text(
        json.dumps(
            {
                "channel": "worker_logs",
                "data": {
                    "worker_id": worker_id,
                    "items": events,
                },
            }
        )
    )


async def _push_job_trace(
    websocket: WebSocket,
    *,
    job_id: str,
) -> None:
    from app.repositories.audio_compute import (
        AudioComputeRepository,
    )

    async with AsyncSessionLocal() as session:
        repo = AudioComputeRepository(session)
        job = await repo.get_job(job_id)
        if job is None:
            await websocket.send_text(
                json.dumps(
                    {
                        "channel": "job_trace",
                        "data": {
                            "job_id": job_id,
                            "error": "not_found",
                        },
                    }
                )
            )
            return
        audit = await repo.list_audit(
            limit=200,
        )
    job_audit = [
        {
            "id": row.id,
            "worker_id": row.worker_id,
            "action": row.action,
            "status_code": row.status_code,
            "meta": row.meta,
            "created_at": (
                row.created_at.isoformat()
                if row.created_at
                else None
            ),
        }
        for row in audit
        if row.job_id == job_id
    ]
    payload = {
        "job_id": job.id,
        "track_id": job.track_id,
        "status": job.status,
        "current_tier": job.current_tier,
        "tiers_planned": job.tiers_planned or [],
        "tier_attempts": job.tier_attempts or [],
        "routed_to_worker": job.routed_to_worker,
        "attempts": job.attempts,
        "error": job.error,
        "audit": job_audit,
        "created_at": (
            job.created_at.isoformat()
            if job.created_at
            else None
        ),
        "finished_at": (
            job.finished_at.isoformat()
            if job.finished_at
            else None
        ),
    }
    await websocket.send_text(
        json.dumps(
            {
                "channel": "job_trace",
                "data": payload,
            }
        )
    )


def _is_ws_open(websocket: WebSocket) -> bool:
    return (
        websocket.client_state == WebSocketState.CONNECTED
        and websocket.application_state == WebSocketState.CONNECTED
    )


async def _broadcast_loop(
    websocket: WebSocket,
    subscriptions: set[str],
    state: dict[str, Any],
) -> None:
    last_task_seen = [""]
    log_since = [int(time.time() * 1_000_000_000)]
    worker_log_cursor = [
        state.get("worker_logs_last_id", "$"),
    ]
    while True:
        if not _is_ws_open(websocket):
            return
        try:
            if "overview" in subscriptions:
                await _push_overview(websocket)
            if "containers" in subscriptions:
                await _push_containers(websocket)
            if "tasks_progress" in subscriptions:
                await _push_tasks_progress(
                    websocket,
                    last_seen_id=last_task_seen,
                )
            if (
                "worker_logs" in subscriptions
                and state.get("worker_logs_id")
            ):
                await _push_worker_logs(
                    websocket,
                    worker_id=state["worker_logs_id"],
                    last_id=worker_log_cursor,
                )
            if (
                "job_trace" in subscriptions
                and state.get("job_trace_id")
            ):
                await _push_job_trace(
                    websocket,
                    job_id=state["job_trace_id"],
                )
            if "logs" in subscriptions:
                await _push_logs(
                    websocket,
                    selectors=state.get(
                        "logs_selectors",
                        {"service": ("dotsound-backend")},
                    ),
                    contains=state.get("logs_contains"),
                    since_ns=log_since,
                )
        except (WebSocketDisconnect, RuntimeError):
            # client gone / close already sent — exit quietly
            return
        except Exception:
            logger.exception("admin_ws_push_failed")
            if not _is_ws_open(websocket):
                return
        pause_s = (
            0.35
            if (
                "worker_logs" in subscriptions
                and state.get("worker_logs_id")
            )
            else 3.0
        )
        await asyncio.sleep(pause_s)


@router.websocket("")
async def admin_ws(
    websocket: WebSocket,
    token: str | None = Query(None),
) -> None:
    if await reject_if_bad_origin(websocket):
        return
    raw_token = token or ""
    proto = websocket.headers.get("sec-websocket-protocol")
    if not raw_token and proto:
        raw_token = proto.split(",")[0].strip()
    auth = await _authenticate(raw_token)
    if auth is None:
        await websocket.close(code=4401)
        return
    user_id, _device_id = auth
    if not await _acquire_ws_slot(user_id):
        logger.warning("admin_ws_quota_exceeded", user_id=user_id)
        await websocket.close(code=4429)
        return
    if proto:
        await websocket.accept(subprotocol=proto)
    else:
        await websocket.accept()
    ws_gauge_inc()
    subscriptions: set[str] = {"overview"}
    state: dict[str, Any] = {
        "logs_selectors": {"service": "dotsound-backend"},
        "logs_contains": None,
    }
    push_task = asyncio.create_task(
        _broadcast_loop(websocket, subscriptions, state)
    )
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "channel": "system",
                    "data": {
                        "type": "hello",
                        "ttl": (ADMIN_SESSION_TTL_SECONDS),
                        "channels": sorted(ALLOWED_CHANNELS),
                    },
                }
            )
        )
        while True:
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,
                )
            except TimeoutError:
                await websocket.send_text(
                    json.dumps(
                        {
                            "channel": "system",
                            "data": {"type": "ping"},
                        }
                    )
                )
                continue
            try:
                msg: dict[str, Any] = json.loads(raw)
            except Exception:
                continue
            cmd = str(msg.get("type", ""))
            channel = str(msg.get("channel", ""))
            if cmd == "subscribe":
                if channel in ALLOWED_CHANNELS:
                    subscriptions.add(channel)
                    if channel == "logs":
                        (
                            state["logs_selectors"],
                            state["logs_contains"],
                        ) = _parse_log_subscribe(msg)
                    if channel == "worker_logs":
                        wid = msg.get("worker_id")
                        if (
                            isinstance(wid, str)
                            and wid.startswith("w_")
                        ):
                            state["worker_logs_id"] = wid
                            state["worker_logs_last_id"] = "$"
                    if channel == "job_trace":
                        jid = msg.get("job_id")
                        if (
                            isinstance(jid, str)
                            and jid.startswith("lj_")
                        ):
                            state["job_trace_id"] = jid
            elif cmd == "unsubscribe":
                subscriptions.discard(channel)
                if channel == "worker_logs":
                    state.pop("worker_logs_id", None)
                if channel == "job_trace":
                    state.pop("job_trace_id", None)
            elif cmd == "logs.update_filter" and "logs" in subscriptions:
                (
                    state["logs_selectors"],
                    state["logs_contains"],
                ) = _parse_log_subscribe(msg)
            elif cmd == "ping":
                await websocket.send_text(
                    json.dumps(
                        {
                            "channel": "system",
                            "data": {
                                "type": "pong",
                                "ts": int(time.time()),
                            },
                        }
                    )
                )
    except Exception:
        logger.info(
            "admin_ws_disconnected",
            user_id=user_id,
        )
    finally:
        push_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await push_task
        ws_gauge_dec()
        await _release_ws_slot(user_id)
        with contextlib.suppress(Exception):
            await websocket.close(code=ws_status.WS_1000_NORMAL_CLOSURE)
