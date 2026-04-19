"""Admin WebSocket endpoint for live updates.

Multiplexes channels (online_users, containers, alerts) over a
single connection. Auth uses an admin JWT in the
``Sec-WebSocket-Protocol`` header (or ``token`` query param as a
fallback). The token is validated through the same machinery as
HTTP requests, including session-active and device-trusted checks.
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

from app.core.auth import (
    AuthError,
    decode_admin_token,
)
from app.core.db import AsyncSessionLocal
from app.core.observability import (
    ws_gauge_dec,
    ws_gauge_inc,
)
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

router = APIRouter(prefix="/ws", tags=["admin-ws"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

ALLOWED_CHANNELS: frozenset[str] = frozenset(
    {
        "overview",
        "containers",
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


async def _broadcast_loop(
    websocket: WebSocket,
    subscriptions: set[str],
) -> None:
    while True:
        try:
            if "overview" in subscriptions:
                await _push_overview(websocket)
            if "containers" in subscriptions:
                await _push_containers(websocket)
        except Exception:
            logger.exception("admin_ws_push_failed")
        await asyncio.sleep(5)


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
    push_task = asyncio.create_task(_broadcast_loop(websocket, subscriptions))
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "channel": "system",
                    "data": {
                        "type": "hello",
                        "ttl": (ADMIN_SESSION_TTL_SECONDS),
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
            if cmd == "subscribe":
                channel = str(msg.get("channel", ""))
                if channel in ALLOWED_CHANNELS:
                    subscriptions.add(channel)
            elif cmd == "unsubscribe":
                channel = str(msg.get("channel", ""))
                subscriptions.discard(channel)
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
