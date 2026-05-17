"""Safely purge stale pending compute_jobs that cannot be claimed.

By default runs in DRY-RUN mode — prints what would be deleted, does nothing.
Pass --execute to actually delete rows.

What is purged:
  - Only PENDING rows (status='pending')
  - Only PREFER_WORKER routing types — these have local fallbacks and will
    be re-enqueued automatically on the next sync/enrichment cycle.
  - Age threshold: older than --min-hours (default 24 h).

What is NEVER purged by this script:
  - WORKER_ONLY types (track_audio_features, audio_embedding,
    artist_features_update, artist_similarity, track_similarity)
    — these require the remote worker and have no local fallback.
  - Claimed / succeeded / failed rows.

Usage:
    poetry run python scripts/purge_stale_compute_jobs.py
    poetry run python scripts/purge_stale_compute_jobs.py --execute
    poetry run python scripts/purge_stale_compute_jobs.py --execute --min-hours 48
    poetry run python scripts/purge_stale_compute_jobs.py --execute --job-type sc_artist_catalog_sync
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

import app.models  # noqa: F401
from app.core.db import AsyncSessionLocal
from app.models.compute_job import ComputeJob
from app.services import compute_queue_service as q
from dotsound_private_core.services.compute_job_policy import (
    RoutingMode,
    get_job_rule,
    requires_worker,
)


def _prefer_worker_types() -> frozenset[str]:
    return frozenset(
        jt
        for jt in q.OFFLOADABLE_JOB_TYPES
        if not requires_worker(jt)
        and get_job_rule(jt).routing is RoutingMode.PREFER_WORKER
    )


async def main(
    *,
    dry_run: bool,
    min_hours: int,
    only_job_type: str | None,
) -> None:
    prefer_worker = _prefer_worker_types()
    cutoff = datetime.now(UTC) - timedelta(hours=min_hours)

    if only_job_type:
        canon = q.canonical_job_type(only_job_type)
        if canon not in prefer_worker:
            print(
                f"ERROR: '{canon}' is not a PREFER_WORKER type or is not "
                f"offloadable.  Refusing to purge.\n"
                f"Safe PREFER_WORKER types: {', '.join(sorted(prefer_worker))}"
            )
            sys.exit(1)
        target_types: frozenset[str] = frozenset({canon})
    else:
        target_types = prefer_worker

    print(f"\nMode: {'DRY-RUN (pass --execute to delete)' if dry_run else '!!! EXECUTE — will DELETE rows !!!'}")
    print(f"Cutoff age: >{min_hours}h  (next_attempt_at < {cutoff.isoformat()})")
    print(f"Target job_types: {', '.join(sorted(target_types))}\n")

    async with AsyncSessionLocal() as session:
        count_rows = (
            await session.execute(
                select(
                    ComputeJob.job_type,
                    func.count(ComputeJob.id).label("cnt"),
                )
                .where(
                    ComputeJob.status == q.STATUS_PENDING,
                    ComputeJob.job_type.in_(sorted(target_types)),
                    ComputeJob.next_attempt_at < cutoff,
                )
                .group_by(ComputeJob.job_type)
            )
        ).all()

        if not count_rows:
            print("Nothing to purge — no matching rows found.")
            return

        total = 0
        for jt, cnt in count_rows:
            print(f"  {jt:<45} {cnt:>8} rows")
            total += int(cnt)
        print(f"  {'TOTAL':<45} {total:>8} rows\n")

        if dry_run:
            print("Dry-run complete. No rows deleted.")
            print("Re-run with --execute to delete.\n")
            return

        confirm = input(
            f"About to DELETE {total:,} rows from compute_jobs.\n"
            "Type 'yes' to confirm: "
        )
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return

        deleted = 0
        for jt, _ in count_rows:
            stmt = delete(ComputeJob).where(
                ComputeJob.status == q.STATUS_PENDING,
                ComputeJob.job_type == jt,
                ComputeJob.next_attempt_at < cutoff,
            )
            res = await session.execute(stmt)
            deleted += int(res.rowcount or 0)

        await session.commit()
        print(f"\nDeleted {deleted:,} rows. Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Purge stale pending PREFER_WORKER compute_jobs."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually delete rows (default: dry-run only).",
    )
    parser.add_argument(
        "--min-hours",
        type=int,
        default=24,
        metavar="N",
        help="Only delete rows older than N hours (default: 24).",
    )
    parser.add_argument(
        "--job-type",
        default=None,
        metavar="TYPE",
        help="Limit to one specific job_type (e.g. sc_artist_catalog_sync).",
    )
    args = parser.parse_args()

    asyncio.run(
        main(
            dry_run=not args.execute,
            min_hours=args.min_hours,
            only_job_type=args.job_type,
        )
    )
