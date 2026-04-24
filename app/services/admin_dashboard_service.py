"""High-level KPIs for the admin dashboard."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.complaint import Complaint
from app.models.lyrics_job import LyricsJob
from app.models.track import Track
from app.models.user import User

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

CACHE_KEY = "admin:dashboard:overview"
CACHE_TTL_SECONDS = 10


async def _safe_count(
    session: AsyncSession,
    statement: Any,  # noqa: ANN401
) -> int:
    try:
        result = await session.execute(statement)
        return int(result.scalar_one() or 0)
    except Exception:
        logger.exception("admin_dashboard_count_failed")
        return 0


_PRESENCE_PREFIX = "presence:"


async def _online_users_count() -> int:
    """Count users with WebSocket presence status *online* in Redis.

    Keys are ``presence:{user_id}`` (see :mod:`app.core.ws_manager`); the
    legacy ``ws:user:*`` pattern was never used and always returned 0.
    """
    redis = get_redis_client()
    online = 0
    try:
        async for key in redis.scan_iter(match=f"{_PRESENCE_PREFIX}*"):
            raw = await redis.get(key)
            if not raw:
                continue
            try:
                data = json.loads(
                    raw if isinstance(raw, str) else raw.decode()
                )
            except (TypeError, ValueError, UnicodeError):
                continue
            if data.get("status") == "online":
                online += 1
    except Exception:
        logger.exception("admin_dashboard_online_count_failed")
        return 0
    return online


async def collect_overview(
    session: AsyncSession,
    *,
    use_cache: bool = True,
) -> dict[str, Any]:
    redis = get_redis_client()
    if use_cache:
        cached = await redis.get(CACHE_KEY)
        if cached:
            try:
                return dict(
                    json.loads(
                        cached if isinstance(cached, str) else cached.decode()
                    )
                )
            except Exception:
                pass

    now = datetime.now(UTC)
    day_ago = now - timedelta(days=1)
    hour_ago = now - timedelta(hours=1)

    users_total = await _safe_count(session, select(func.count(User.id)))
    users_active = await _safe_count(
        session,
        select(func.count(User.id)).where(User.is_active.is_(True)),
    )
    users_admins = await _safe_count(
        session,
        select(func.count(User.id)).where(User.is_admin.is_(True)),
    )
    users_new_24h = await _safe_count(
        session,
        select(func.count(User.id)).where(User.created_at >= day_ago),
    )

    tracks_total = await _safe_count(session, select(func.count(Track.id)))
    tracks_active = await _safe_count(
        session,
        select(func.count(Track.id)).where(Track.is_active.is_(True)),
    )
    tracks_new_24h = await _safe_count(
        session,
        select(func.count(Track.id)).where(Track.created_at >= day_ago),
    )

    complaints_open = await _safe_count(
        session,
        select(func.count(Complaint.id)).where(
            Complaint.is_resolved.is_(False)
        ),
    )

    jobs_active = await _safe_count(
        session,
        select(func.count(LyricsJob.id)).where(
            LyricsJob.status.in_(["queued", "running"])
        ),
    )
    jobs_failed_1h = await _safe_count(
        session,
        select(func.count(LyricsJob.id)).where(
            LyricsJob.status == "error",
            LyricsJob.created_at >= hour_ago,
        ),
    )

    s3_bytes = 0
    try:
        result = await session.execute(
            select(func.coalesce(func.sum(Track.file_size_bytes), 0))
        )
        s3_bytes = int(result.scalar_one() or 0)
    except Exception:
        logger.exception("admin_dashboard_s3_size_failed")

    online_now = await _online_users_count()

    payload = {
        "generated_at": int(time.time()),
        "users": {
            "total": users_total,
            "active": users_active,
            "admins": users_admins,
            "new_24h": users_new_24h,
            "online_now": online_now,
        },
        "tracks": {
            "total": tracks_total,
            "active": tracks_active,
            "new_24h": tracks_new_24h,
            "storage_bytes": s3_bytes,
        },
        "complaints": {
            "open": complaints_open,
        },
        "jobs": {
            "active": jobs_active,
            "failed_1h": jobs_failed_1h,
        },
    }
    try:
        await redis.setex(
            CACHE_KEY,
            CACHE_TTL_SECONDS,
            json.dumps(payload),
        )
    except Exception:
        logger.exception("admin_dashboard_cache_failed")
    return payload
