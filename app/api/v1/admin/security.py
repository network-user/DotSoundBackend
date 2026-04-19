"""Admin security insight endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.dependencies import (
    get_db,
    require_capability,
    require_step_up,
)
from app.models.user import User
from app.repositories.admin_login_attempt import (
    AdminLoginAttemptRepository,
)
from app.services.admin_auth_service import (
    LOCKOUT_REDIS_PREFIX,
    release_lockout,
)

router = APIRouter(prefix="/security", tags=["admin-security"])


@router.get("/login-attempts")
async def login_attempts(
    failed_only: bool = Query(False),
    minutes: int = Query(60, ge=1, le=10_080),
    limit: int = Query(200, ge=1, le=1000),
    _admin: User = Depends(require_capability("security.view")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(minutes=minutes)
    repo = AdminLoginAttemptRepository(session)
    rows = await repo.list_recent(
        failed_only=failed_only,
        since=since,
        limit=limit,
    )
    return {
        "items": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "ip": row.ip,
                "ua": row.ua,
                "success": row.success,
                "reason": row.reason,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "since": since,
    }


@router.get("/locked-users")
async def locked_users(
    _admin: User = Depends(require_capability("security.view")),
) -> dict[str, Any]:
    redis = get_redis_client()
    try:
        keys = await redis.keys(f"{LOCKOUT_REDIS_PREFIX}*")
    except Exception:
        keys = []
    items: list[dict[str, Any]] = []
    for key in keys:
        try:
            ttl = await redis.ttl(key)
        except Exception:
            ttl = None
        try:
            user_id_part = (
                key.decode() if isinstance(key, bytes) else key
            ).removeprefix(LOCKOUT_REDIS_PREFIX)
            user_id = int(user_id_part)
        except Exception:
            continue
        items.append(
            {
                "user_id": user_id,
                "ttl_seconds": ttl,
            }
        )
    return {"items": items}


@router.post("/lockout/{user_id}/release")
async def release(
    user_id: int,
    _admin: User = Depends(require_step_up("security.lockout.release")),
) -> dict[str, Any]:
    released = await release_lockout(user_id)
    return {
        "user_id": user_id,
        "released": released,
    }


_ANTI_ABUSE_STREAM = "anti_abuse:events"


@router.get("/anti-abuse-events")
async def anti_abuse_events(
    limit: int = Query(100, ge=1, le=500),
    _admin: User = Depends(require_capability("security.view")),
) -> dict[str, Any]:
    """Read recent anti-abuse events from Redis stream.

    PrivateCore writes events to ``anti_abuse:events`` stream
    (Tor-detected, disposable email, content flagged, etc.).
    Backend just reads them; algorithms stay in PrivateCore.
    """
    redis = get_redis_client()
    items: list[dict[str, Any]] = []
    try:
        raw = await redis.xrevrange(_ANTI_ABUSE_STREAM, count=limit)
    except Exception:
        raw = []
    for entry_id, fields in raw:
        try:
            entry_id_str = (
                entry_id.decode()
                if isinstance(entry_id, bytes)
                else str(entry_id)
            )
            decoded: dict[str, Any] = {}
            for key, value in fields.items():
                k = key.decode() if isinstance(key, bytes) else str(key)
                v = value.decode() if isinstance(value, bytes) else str(value)
                decoded[k] = v
            items.append(
                {
                    "id": entry_id_str,
                    "data": decoded,
                }
            )
        except Exception:
            continue
    return {"items": items, "count": len(items)}
