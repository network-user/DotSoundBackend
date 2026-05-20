"""High-level KPIs for the admin dashboard."""

from __future__ import annotations

import inspect
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.admin_action_log import AdminActionLog
from app.models.background_job import BackgroundJob
from app.models.complaint import Complaint
from app.models.compute_job import ComputeJob
from app.models.listen_event import ListenEvent
from app.models.lyrics_job import LyricsJob
from app.models.track import Track
from app.models.user import User
from app.models.user_preference import UserPreference

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

    users_total = 0
    users_active = 0
    users_admins = 0
    users_new_24h = 0
    try:
        row = (
            await session.execute(
                select(
                    func.count(User.id),
                    func.sum(case((User.is_active.is_(True), 1), else_=0)),
                    func.sum(case((User.is_admin.is_(True), 1), else_=0)),
                    func.sum(case((User.created_at >= day_ago, 1), else_=0)),
                )
            )
        ).first()
        if row is not None:
            users_total = int(row[0] or 0)
            users_active = int(row[1] or 0)
            users_admins = int(row[2] or 0)
            users_new_24h = int(row[3] or 0)
    except Exception:
        logger.exception("admin_dashboard_user_counts_failed")

    tracks_total = 0
    tracks_active = 0
    tracks_new_24h = 0
    try:
        row = (
            await session.execute(
                select(
                    func.count(Track.id),
                    func.sum(case((Track.is_active.is_(True), 1), else_=0)),
                    func.sum(case((Track.created_at >= day_ago, 1), else_=0)),
                )
            )
        ).first()
        if row is not None:
            tracks_total = int(row[0] or 0)
            tracks_active = int(row[1] or 0)
            tracks_new_24h = int(row[2] or 0)
    except Exception:
        logger.exception("admin_dashboard_track_counts_failed")

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


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _bucket_timestamp(
    value: datetime,
    *,
    start_ts: int,
    bucket_seconds: int,
) -> int:
    ts = int(_as_aware(value).timestamp())
    if ts <= start_ts:
        return start_ts
    offset = ((ts - start_ts) // bucket_seconds) * bucket_seconds
    return start_ts + offset


async def collect_compute_job_stats(
    session: AsyncSession,
    *,
    period_hours: int,
    bucket_minutes: int,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    hours = max(1, min(720, int(period_hours)))
    minutes = max(5, min(1440, int(bucket_minutes)))
    start = now - timedelta(hours=hours)
    start_ts = int(start.timestamp())
    end_ts = int(now.timestamp())
    bucket_seconds = minutes * 60

    status_rows = await session.execute(
        select(
            ComputeJob.status,
            func.count(ComputeJob.id),
        ).group_by(ComputeJob.status)
    )
    by_status = {
        str(status): int(count or 0) for status, count in status_rows.all()
    }
    total = sum(by_status.values())
    succeeded_total = by_status.get("succeeded", 0)
    failed_total = by_status.get("failed", 0)
    pending = by_status.get("pending", 0)
    claimed = by_status.get("claimed", 0)

    succeeded_period = await _safe_count(
        session,
        select(func.count(ComputeJob.id)).where(
            ComputeJob.status == "succeeded",
            ComputeJob.finished_at >= start,
        ),
    )
    failed_period = await _safe_count(
        session,
        select(func.count(ComputeJob.id)).where(
            ComputeJob.status == "failed",
            ComputeJob.finished_at >= start,
        ),
    )

    bucket_count = max(1, ((end_ts - start_ts) // bucket_seconds) + 1)
    buckets: dict[int, dict[str, int]] = {
        start_ts
        + (idx * bucket_seconds): {
            "created": 0,
            "succeeded": 0,
            "failed": 0,
            "resolved": 0,
        }
        for idx in range(bucket_count)
    }
    rows = await session.execute(
        select(
            ComputeJob.status,
            ComputeJob.created_at,
            ComputeJob.finished_at,
        )
        .where(
            or_(
                ComputeJob.created_at >= start,
                ComputeJob.finished_at >= start,
            )
        )
        .limit(100_000)
    )
    for status, created_at, finished_at in rows.all():
        if isinstance(created_at, datetime):
            bucket = _bucket_timestamp(
                created_at,
                start_ts=start_ts,
                bucket_seconds=bucket_seconds,
            )
            if bucket in buckets:
                buckets[bucket]["created"] += 1
        if not isinstance(finished_at, datetime):
            continue
        bucket = _bucket_timestamp(
            finished_at,
            start_ts=start_ts,
            bucket_seconds=bucket_seconds,
        )
        if bucket not in buckets:
            continue
        if status == "succeeded":
            buckets[bucket]["succeeded"] += 1
            buckets[bucket]["resolved"] += 1
        elif status == "failed":
            buckets[bucket]["failed"] += 1
            buckets[bucket]["resolved"] += 1

    return {
        "generated_at": int(now.timestamp()),
        "period_hours": hours,
        "bucket_minutes": minutes,
        "total": total,
        "by_status": by_status,
        "pending": pending,
        "claimed": claimed,
        "succeeded_total": succeeded_total,
        "failed_total": failed_total,
        "resolved_total": succeeded_total + failed_total,
        "succeeded_period": succeeded_period,
        "failed_period": failed_period,
        "resolved_period": succeeded_period + failed_period,
        "buckets": [
            {
                "ts": ts,
                **values,
            }
            for ts, values in sorted(buckets.items())
        ],
    }


_TASKIQ_ACTIVE_STATUSES: tuple[str, ...] = ("queued", "running", "cancelling")
_TASKIQ_DONE_STATUS = "done"
_TASKIQ_FAILED_STATUSES: tuple[str, ...] = ("failed", "failed_terminal")
_TASKIQ_CANCELLED_STATUS = "cancelled"


async def _taskiq_queue_lengths() -> dict[str, int]:
    """Return Redis queue length per Taskiq queue key.

    Reads ``taskiq:*`` lists. Falls back to empty mapping if Redis is
    unavailable; the dashboard then shows zero queues rather than 500.
    """
    out: dict[str, int] = {}
    try:
        redis = get_redis_client()
        keys = await redis.keys("taskiq:*")
        for raw in keys:
            key = raw.decode() if isinstance(raw, bytes) else str(raw)
            try:
                length = int(await redis.llen(key) or 0)
            except Exception:
                length = 0
            out[key] = length
    except Exception:
        logger.warning("admin_dashboard_taskiq_queues_unavailable")
    return out


async def collect_taskiq_stats(
    session: AsyncSession,
    *,
    period_hours: int,
    bucket_minutes: int,
) -> dict[str, Any]:
    """Mirror of :func:`collect_compute_job_stats` but for ``background_jobs``.

    Source of truth is the unified ``background_jobs`` table (one row per
    ``enqueue()`` call, status updated by the Taskiq lifecycle middleware).
    Adds Redis queue lengths so the panel can show ``in_queue`` vs
    ``running`` separately — ``queued`` rows whose Taskiq message was lost
    are still counted in ``queued`` here.
    """
    now = datetime.now(UTC)
    hours = max(1, min(720, int(period_hours)))
    minutes = max(5, min(1440, int(bucket_minutes)))
    start = now - timedelta(hours=hours)
    start_ts = int(start.timestamp())
    end_ts = int(now.timestamp())
    bucket_seconds = minutes * 60

    status_rows = await session.execute(
        select(
            BackgroundJob.status,
            func.count(BackgroundJob.id),
        ).group_by(BackgroundJob.status)
    )
    by_status = {
        str(status): int(count or 0) for status, count in status_rows.all()
    }
    total = sum(by_status.values())
    queued = by_status.get("queued", 0)
    running = by_status.get("running", 0)
    cancelling = by_status.get("cancelling", 0)
    succeeded_total = by_status.get(_TASKIQ_DONE_STATUS, 0)
    failed_total = sum(by_status.get(s, 0) for s in _TASKIQ_FAILED_STATUSES)
    cancelled_total = by_status.get(_TASKIQ_CANCELLED_STATUS, 0)

    succeeded_period = await _safe_count(
        session,
        select(func.count(BackgroundJob.id)).where(
            BackgroundJob.status == _TASKIQ_DONE_STATUS,
            BackgroundJob.finished_at >= start,
        ),
    )
    failed_period = await _safe_count(
        session,
        select(func.count(BackgroundJob.id)).where(
            BackgroundJob.status.in_(_TASKIQ_FAILED_STATUSES),
            BackgroundJob.finished_at >= start,
        ),
    )

    bucket_count = max(1, ((end_ts - start_ts) // bucket_seconds) + 1)
    buckets: dict[int, dict[str, int]] = {
        start_ts
        + (idx * bucket_seconds): {
            "created": 0,
            "succeeded": 0,
            "failed": 0,
            "resolved": 0,
        }
        for idx in range(bucket_count)
    }
    rows = await session.execute(
        select(
            BackgroundJob.status,
            BackgroundJob.created_at,
            BackgroundJob.finished_at,
        )
        .where(
            or_(
                BackgroundJob.created_at >= start,
                BackgroundJob.finished_at >= start,
            )
        )
        .limit(100_000)
    )
    for status, created_at, finished_at in rows.all():
        if isinstance(created_at, datetime):
            bucket = _bucket_timestamp(
                created_at,
                start_ts=start_ts,
                bucket_seconds=bucket_seconds,
            )
            if bucket in buckets:
                buckets[bucket]["created"] += 1
        if not isinstance(finished_at, datetime):
            continue
        bucket = _bucket_timestamp(
            finished_at,
            start_ts=start_ts,
            bucket_seconds=bucket_seconds,
        )
        if bucket not in buckets:
            continue
        if status == _TASKIQ_DONE_STATUS:
            buckets[bucket]["succeeded"] += 1
            buckets[bucket]["resolved"] += 1
        elif status in _TASKIQ_FAILED_STATUSES:
            buckets[bucket]["failed"] += 1
            buckets[bucket]["resolved"] += 1

    queue_lengths = await _taskiq_queue_lengths()
    in_redis_total = sum(queue_lengths.values())

    return {
        "generated_at": int(now.timestamp()),
        "period_hours": hours,
        "bucket_minutes": minutes,
        "total": total,
        "by_status": by_status,
        "queued": queued,
        "running": running,
        "cancelling": cancelling,
        "cancelled_total": cancelled_total,
        "in_redis_total": in_redis_total,
        "queue_lengths": queue_lengths,
        "succeeded_total": succeeded_total,
        "failed_total": failed_total,
        "resolved_total": succeeded_total + failed_total,
        "succeeded_period": succeeded_period,
        "failed_period": failed_period,
        "resolved_period": succeeded_period + failed_period,
        "buckets": [
            {
                "ts": ts,
                **values,
            }
            for ts, values in sorted(buckets.items())
        ],
    }


async def purge_pending_compute_jobs(
    session: AsyncSession,
    *,
    older_than_hours: int,
) -> dict[str, int]:
    """Hard-delete ``pending`` ComputeJob rows older than the cutoff.

    Used as an admin escape hatch when the offload worker is offline
    and pending jobs accumulate beyond what the reaper can drain. Only
    affects ``status='pending'`` rows; claimed/succeeded/failed are
    left untouched. Returns ``{"deleted": N, "remaining_pending": M}``.
    """
    from sqlalchemy import delete

    hours = max(1, int(older_than_hours))
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    result = await session.execute(
        delete(ComputeJob).where(
            ComputeJob.status == "pending",
            ComputeJob.created_at < cutoff,
        )
    )
    await session.commit()
    deleted = int(result.rowcount or 0)

    remaining = await _safe_count(
        session,
        select(func.count(ComputeJob.id)).where(
            ComputeJob.status == "pending"
        ),
    )
    logger.warning(
        "admin_dashboard_compute_jobs_purged",
        deleted=deleted,
        older_than_hours=hours,
        remaining_pending=remaining,
    )
    return {
        "deleted": deleted,
        "older_than_hours": hours,
        "remaining_pending": remaining,
    }


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
        names_stmt = select(Track.id, Track.title).where(
            Track.id.in_(track_ids)
        )
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
    top_stmt = base_listen.order_by(func.count(ListenEvent.id).desc()).limit(
        15
    )
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
        uploads_series_stmt = uploads_series_stmt.where(
            Track.created_at >= start
        )
    uploads_series_stmt = uploads_series_stmt.order_by(
        func.date(Track.created_at)
    )
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

    unique_admins_stmt = select(
        func.count(func.distinct(AdminActionLog.user_id))
    )
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
            select(User.id, User.username, User.email).where(
                User.id.in_(admin_ids)
            )
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


async def collect_activation_funnel(
    session: AsyncSession,
    *,
    period: str,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    start = _period_start(now, period)
    redis = get_redis_client()

    first_day = (start or (now - timedelta(days=6))).date()
    last_day = now.date()
    day = first_day

    users_by_event = {
        "auth_success": 0,
        "onboarding_complete": 0,
        "onboarding_skip": 0,
        "home_first_play": 0,
        "home_first_session_start": 0,
    }
    counters_by_event = {
        "auth_success": 0,
        "onboarding_complete": 0,
        "onboarding_skip": 0,
        "home_first_play": 0,
        "home_first_session_start": 0,
    }

    while day <= last_day:
        suffix = day.strftime("%Y%m%d")
        counter_key = f"activation:counters:{suffix}"
        counter_values_raw = redis.hgetall(counter_key)
        if inspect.isawaitable(counter_values_raw):
            counter_values = await counter_values_raw
        else:
            counter_values = counter_values_raw
        for key in counters_by_event:
            raw = counter_values.get(key)
            counters_by_event[key] += int(raw or 0)
            set_key = f"activation:users:{suffix}:{key}"
            scard_raw = redis.scard(set_key)
            if inspect.isawaitable(scard_raw):
                scard = await scard_raw
            else:
                scard = scard_raw
            users_by_event[key] += int(scard)
        day += timedelta(days=1)

    time_stmt = select(
        func.avg(
            func.extract(
                "epoch",
                UserPreference.first_play_at
                - UserPreference.auth_first_seen_at,
            )
        )
    ).where(
        UserPreference.auth_first_seen_at.is_not(None),
        UserPreference.first_play_at.is_not(None),
    )
    if start is not None:
        time_stmt = time_stmt.where(UserPreference.auth_first_seen_at >= start)
    avg_seconds_res = await session.execute(time_stmt)
    avg_seconds_raw = avg_seconds_res.scalar_one_or_none()
    avg_seconds = float(avg_seconds_raw or 0.0)

    onboarding_total = (
        users_by_event["onboarding_complete"]
        + users_by_event["onboarding_skip"]
    )
    skip_rate = (
        users_by_event["onboarding_skip"] / onboarding_total
        if onboarding_total
        else 0.0
    )

    return {
        "period": period,
        "from_ts": int(start.timestamp()) if start is not None else None,
        "to_ts": int(now.timestamp()),
        "users": users_by_event,
        "events": counters_by_event,
        "avg_auth_to_first_play_seconds": round(avg_seconds, 2),
        "skip_rate": round(skip_rate, 4),
        "first_session_plays_count": counters_by_event["home_first_play"]
        + counters_by_event["home_first_session_start"],
    }
