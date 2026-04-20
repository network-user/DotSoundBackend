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
from sqlalchemy import desc, select
from starlette.websockets import WebSocketDisconnect, WebSocketState

from app.core.auth import (
    AuthError,
    decode_admin_token,
)
from app.core.db import AsyncSessionLocal
from app.core.observability import (
    ws_gauge_dec,
    ws_gauge_inc,
)
from app.models.lyrics_job import LyricsJob
from app.repositories.admin_device import (
    AdminDeviceRepository,
)
from app.repositories.admin_session import (
    AdminSessionRepository,
)
from app.services.admin_dashboard_service import (
    collect_overview,
)
from app.services.container_health_service import (
    get_container_summary,
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
    }
)


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
        result = await session.execute(
            select(LyricsJob)
            .where(
                LyricsJob.status.in_(
                    [
                        "queued",
                        "running",
                        "error",
                        "done",
                    ]
                )
            )
            .order_by(desc(LyricsJob.updated_at))
            .limit(40)
        )
        rows = list(result.scalars().all())
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
        await asyncio.sleep(3)


@router.websocket("")
async def admin_ws(
    websocket: WebSocket,
    token: str | None = Query(None),
) -> None:
    raw_token = token or ""
    proto = websocket.headers.get("sec-websocket-protocol")
    if not raw_token and proto:
        raw_token = proto.split(",")[0].strip()
    auth = await _authenticate(raw_token)
    if auth is None:
        await websocket.close(code=4401)
        return
    user_id, _device_id = auth
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
            elif cmd == "unsubscribe":
                subscriptions.discard(channel)
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
        with contextlib.suppress(Exception):
            await websocket.close(code=ws_status.WS_1000_NORMAL_CLOSURE)
