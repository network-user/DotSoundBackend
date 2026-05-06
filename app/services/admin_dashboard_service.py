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
from app.models.admin_action_log import AdminActionLog
from app.models.lyrics_job import LyricsJob
from app.models.listen_event import ListenEvent
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


def _period_start(now: datetime, period: str) -> datetime | None:
    if period == "all":
        return None
    if period == "today":
        return datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            tzinfo=UTC,
        )
    if period == "7d":
        return now - timedelta(days=7)
    if period == "30d":
        return now - timedelta(days=30)
    raise ValueError("unsupported period")


async def collect_stats(
    session: AsyncSession,
    *,
    period: str,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    start = _period_start(now, period)

    users_stmt = select(func.count(User.id))
    tracks_stmt = select(func.count(Track.id))
    listens_stmt = select(func.count(ListenEvent.id))
    unique_stmt = select(func.count(func.distinct(ListenEvent.user_id)))
    complaints_new_stmt = select(func.count(Complaint.id))
    completed_stmt = select(func.count(ListenEvent.id)).where(
        ListenEvent.completed.is_(True)
    )
    skips_stmt = select(func.count(ListenEvent.id)).where(
        ListenEvent.skipped.is_(True)
    )
    top_tracks_stmt = (
        select(
            ListenEvent.track_id.label("track_id"),
            func.count(ListenEvent.id).label("plays"),
            func.count(func.distinct(ListenEvent.user_id)).label(
                "unique_listeners"
            ),
        )
        .group_by(ListenEvent.track_id)
        .order_by(func.count(ListenEvent.id).desc())
        .limit(5)
    )
    if start is not None:
        users_stmt = users_stmt.where(User.created_at >= start)
        tracks_stmt = tracks_stmt.where(Track.created_at >= start)
        listens_stmt = listens_stmt.where(ListenEvent.created_at >= start)
        unique_stmt = unique_stmt.where(ListenEvent.created_at >= start)
        complaints_new_stmt = complaints_new_stmt.where(
            Complaint.created_at >= start
        )
        completed_stmt = completed_stmt.where(ListenEvent.created_at >= start)
        skips_stmt = skips_stmt.where(ListenEvent.created_at >= start)
        top_tracks_stmt = top_tracks_stmt.where(
            ListenEvent.created_at >= start
        )

    users_registered = await _safe_count(session, users_stmt)
    tracks_uploaded = await _safe_count(session, tracks_stmt)
    listens_total = await _safe_count(session, listens_stmt)
    unique_listeners = await _safe_count(session, unique_stmt)
    complaints_new = await _safe_count(session, complaints_new_stmt)
    complaints_open = await _safe_count(
        session,
        select(func.count(Complaint.id)).where(
            Complaint.is_resolved.is_(False)
        ),
    )
    completed_listens = await _safe_count(session, completed_stmt)
    skips = await _safe_count(session, skips_stmt)
    top_rows = await session.execute(top_tracks_stmt)
    raw_top = list(top_rows.all())

    top_tracks: list[dict[str, Any]] = []
    if raw_top:
        track_ids = [int(row.track_id) for row in raw_top]
        names_stmt = select(Track.id, Track.title).where(Track.id.in_(track_ids))
        names_rows = await session.execute(names_stmt)
        names = {int(row.id): str(row.title) for row in names_rows}
        for row in raw_top:
            track_id = int(row.track_id)
            top_tracks.append(
                {
                    "track_id": track_id,
                    "title": names.get(track_id, f"Track #{track_id}"),
                    "plays": int(row.plays or 0),
                    "unique_listeners": int(row.unique_listeners or 0),
                }
            )

    return {
        "period": period,
        "from_ts": int(start.timestamp()) if start is not None else None,
        "to_ts": int(now.timestamp()),
        "users_registered": users_registered,
        "tracks_uploaded": tracks_uploaded,
        "listens_total": listens_total,
        "unique_listeners": unique_listeners,
        "completed_listens": completed_listens,
        "skips": skips,
        "complaints_new": complaints_new,
        "complaints_open": complaints_open,
        "top_tracks": top_tracks,
    }


def _day_to_ts(day_value: Any) -> int | None:  # noqa: ANN401
    if day_value is None:
        return None
    if isinstance(day_value, datetime):
        return int(day_value.replace(tzinfo=UTC).timestamp())
    if hasattr(day_value, "year") and hasattr(day_value, "month"):
        as_dt = datetime(
            day_value.year,
            day_value.month,
            day_value.day,
            tzinfo=UTC,
        )
        return int(as_dt.timestamp())
    try:
        parsed = datetime.fromisoformat(str(day_value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return int(parsed.timestamp())
    except Exception:
        return None


async def collect_track_stats(
    session: AsyncSession,
    *,
    period: str,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    start = _period_start(now, period)

    base_listen = select(
        ListenEvent.track_id.label("track_id"),
        func.count(ListenEvent.id).label("plays"),
        func.count(func.distinct(ListenEvent.user_id)).label(
            "unique_listeners"
        ),
    ).group_by(ListenEvent.track_id)
    if start is not None:
        base_listen = base_listen.where(ListenEvent.created_at >= start)
    top_stmt = base_listen.order_by(func.count(ListenEvent.id).desc()).limit(15)
    top_rows = await session.execute(top_stmt)
    top_raw = list(top_rows.all())

    track_ids = [int(row.track_id) for row in top_raw]
    names: dict[int, str] = {}
    if track_ids:
        names_rows = await session.execute(
            select(Track.id, Track.title).where(Track.id.in_(track_ids))
        )
        names = {int(row.id): str(row.title) for row in names_rows}
    top_tracks = [
        {
            "track_id": int(row.track_id),
            "title": names.get(int(row.track_id), f"Track #{row.track_id}"),
            "plays": int(row.plays or 0),
            "unique_listeners": int(row.unique_listeners or 0),
        }
        for row in top_raw
    ]

    uploads_series_stmt = select(
        func.date(Track.created_at).label("day"),
        func.count(Track.id).label("value"),
    ).group_by(func.date(Track.created_at))
    if start is not None:
        uploads_series_stmt = uploads_series_stmt.where(Track.created_at >= start)
    uploads_series_stmt = uploads_series_stmt.order_by(func.date(Track.created_at))
    uploads_rows = await session.execute(uploads_series_stmt)
    uploads_series: list[dict[str, int]] = []
    for row in uploads_rows:
        ts = _day_to_ts(row.day)
        if ts is None:
            continue
        uploads_series.append({"ts": ts, "value": int(row.value or 0)})

    return {
        "period": period,
        "from_ts": int(start.timestamp()) if start is not None else None,
        "to_ts": int(now.timestamp()),
        "top_tracks": top_tracks,
        "uploads_series": uploads_series,
    }


async def collect_admin_stats(
    session: AsyncSession,
    *,
    period: str,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    start = _period_start(now, period)

    base = select(func.count(AdminActionLog.id))
    if start is not None:
        base = base.where(AdminActionLog.created_at >= start)
    total_actions = await _safe_count(session, base)

    unique_admins_stmt = select(func.count(func.distinct(AdminActionLog.user_id)))
    if start is not None:
        unique_admins_stmt = unique_admins_stmt.where(
            AdminActionLog.created_at >= start
        )
    unique_admins = await _safe_count(session, unique_admins_stmt)

    top_admins_stmt = (
        select(
            AdminActionLog.user_id.label("user_id"),
            func.count(AdminActionLog.id).label("actions"),
        )
        .group_by(AdminActionLog.user_id)
        .order_by(func.count(AdminActionLog.id).desc())
        .limit(10)
    )
    if start is not None:
        top_admins_stmt = top_admins_stmt.where(
            AdminActionLog.created_at >= start
        )
    top_admin_rows = await session.execute(top_admins_stmt)
    top_admin_raw = list(top_admin_rows.all())

    admin_ids = [int(row.user_id) for row in top_admin_raw]
    names: dict[int, str] = {}
    if admin_ids:
        user_rows = await session.execute(
            select(User.id, User.username, User.email).where(User.id.in_(admin_ids))
        )
        names = {
            int(row.id): str(row.username or row.email or f"#{row.id}")
            for row in user_rows
        }
    top_admins = [
        {
            "user_id": int(row.user_id),
            "name": names.get(int(row.user_id), f"#{row.user_id}"),
            "actions": int(row.actions or 0),
        }
        for row in top_admin_raw
    ]

    actions_series_stmt = select(
        func.date(AdminActionLog.created_at).label("day"),
        func.count(AdminActionLog.id).label("value"),
    ).group_by(func.date(AdminActionLog.created_at))
    if start is not None:
        actions_series_stmt = actions_series_stmt.where(
            AdminActionLog.created_at >= start
        )
    actions_series_stmt = actions_series_stmt.order_by(
        func.date(AdminActionLog.created_at)
    )
    actions_rows = await session.execute(actions_series_stmt)
    actions_series: list[dict[str, int]] = []
    for row in actions_rows:
        ts = _day_to_ts(row.day)
        if ts is None:
            continue
        actions_series.append({"ts": ts, "value": int(row.value or 0)})

    return {
        "period": period,
        "from_ts": int(start.timestamp()) if start is not None else None,
        "to_ts": int(now.timestamp()),
        "total_actions": total_actions,
        "unique_admins": unique_admins,
        "top_admins": top_admins,
        "actions_series": actions_series,
    }
