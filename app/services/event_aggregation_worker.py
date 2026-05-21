"""Fold raw ``listen_events`` rows older than the retention window
into ``listen_events_daily`` buckets, then delete the raw rows.

Worker runs once per day from the seeded scheduled job. Aggregation
and deletion happen in lock-step per UTC day so a crash mid-run
leaves the remaining backlog for the next sweep.

Race notes:
- Raw rows use ``created_at`` defaulted server-side at insert time,
  so DELETE with ``created_at < cutoff`` cannot collide with rows
  newly written by playback handlers (their ``created_at`` is fresh).
- UPSERT uses ``listen_events_daily.x + EXCLUDED.x`` semantics; the
  per-day transaction makes the increment safe even if the worker
  is re-run partially.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import text

from app.core import observability
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.services import event_retention_adapter

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


_AGGREGATE_DAY_SQL = text(
    """
    INSERT INTO listen_events_daily (
        day,
        user_id,
        track_id,
        plays,
        listen_seconds,
        completes,
        skips,
        last_seen
    )
    SELECT
        DATE(created_at AT TIME ZONE 'UTC') AS day,
        user_id,
        track_id,
        COUNT(*)::int AS plays,
        COALESCE(SUM(duration_listened_seconds), 0)::bigint
            AS listen_seconds,
        COUNT(*) FILTER (WHERE completed)::int AS completes,
        COUNT(*) FILTER (WHERE skipped)::int AS skips,
        MAX(created_at) AS last_seen
    FROM listen_events
    WHERE created_at >= :day_start
      AND created_at < :day_end
    GROUP BY day, user_id, track_id
    ON CONFLICT (day, user_id, track_id) DO UPDATE SET
        plays = listen_events_daily.plays + EXCLUDED.plays,
        listen_seconds = listen_events_daily.listen_seconds
            + EXCLUDED.listen_seconds,
        completes = listen_events_daily.completes + EXCLUDED.completes,
        skips = listen_events_daily.skips + EXCLUDED.skips,
        last_seen = GREATEST(
            listen_events_daily.last_seen, EXCLUDED.last_seen
        )
    """
)

_DELETE_DAY_SQL = text(
    """
    DELETE FROM listen_events
    WHERE created_at >= :day_start
      AND created_at < :day_end
    """
)

_DISTINCT_DAYS_SQL = text(
    """
    SELECT DISTINCT DATE(created_at AT TIME ZONE 'UTC') AS day
    FROM listen_events
    WHERE created_at < :cutoff
    ORDER BY day
    LIMIT :limit
    """
)


def _day_bounds(day_value: object) -> tuple[datetime, datetime]:
    d = day_value.date() if isinstance(day_value, datetime) else day_value
    if not isinstance(d, date):
        raise TypeError(f"unexpected day type: {type(day_value)!r}")
    start = datetime(d.year, d.month, d.day, tzinfo=UTC)
    return start, start + timedelta(days=1)


@broker.task
async def aggregate_listen_events_task(
    max_days_per_run: int = 14,
) -> dict[str, Any]:
    """Aggregate raw listen_events older than the retention window."""
    retention_days = event_retention_adapter.listen_event_raw_retention_days()
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            _DISTINCT_DAYS_SQL,
            {"cutoff": cutoff, "limit": max_days_per_run},
        )
        days = [row[0] for row in res.all()]

    if not days:
        logger.info(
            "listen_events_aggregation_idle",
            retention_days=retention_days,
        )
        return {
            "retention_days": retention_days,
            "days_processed": 0,
            "rows_deleted": 0,
        }

    total_deleted = 0
    processed_days = 0

    for day_value in days:
        day_start, day_end = _day_bounds(day_value)
        if day_end > cutoff:
            continue
        async with AsyncSessionLocal() as session:
            try:
                await session.execute(
                    _AGGREGATE_DAY_SQL,
                    {"day_start": day_start, "day_end": day_end},
                )
                del_res = await session.execute(
                    _DELETE_DAY_SQL,
                    {"day_start": day_start, "day_end": day_end},
                )
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception(
                    "listen_events_aggregation_day_failed",
                    day=str(day_value),
                )
                continue
            deleted = int(getattr(del_res, "rowcount", 0) or 0)
            total_deleted += deleted
            processed_days += 1
            logger.info(
                "listen_events_aggregation_day_complete",
                day=str(day_value),
                rows_deleted=deleted,
            )

    summary = {
        "retention_days": retention_days,
        "days_processed": processed_days,
        "rows_deleted": total_deleted,
    }
    observability.listen_events_aggregation_observed(
        days_processed=processed_days,
        rows_deleted=total_deleted,
    )
    logger.info("listen_events_aggregation_complete", **summary)
    return summary
