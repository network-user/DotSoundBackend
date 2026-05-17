"""Diagnose why the Compute Worker is not claiming jobs.

Run:
    poetry run python scripts/diagnose_compute_queue.py

Prints:
  - pending/claimed/succeeded/failed counts per job_type
  - whether each type is currently claimable by the worker
  - root cause summary and recommended action
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import func, select, text

import app.models  # noqa: F401  — register ORM mappers
from app.core.db import AsyncSessionLocal
from app.models.compute_job import ComputeJob
from app.services import compute_queue_service as q
from app.services.compute_job_offload_config import (
    should_enqueue_remote,
    worker_claim_enabled,
)
from dotsound_private_core.services.compute_job_policy import (
    RoutingMode,
    get_job_rule,
    requires_worker,
)


def _routing_label(job_type: str) -> str:
    try:
        rule = get_job_rule(job_type)
        return rule.routing.value
    except Exception:
        return "unknown"


async def main() -> None:
    print("\n=== Compute Queue Diagnostics ===\n")

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(
                    ComputeJob.job_type,
                    ComputeJob.status,
                    func.count(ComputeJob.id).label("cnt"),
                ).group_by(ComputeJob.job_type, ComputeJob.status)
            )
        ).all()

    totals: dict[str, dict[str, int]] = {}
    for job_type, status, cnt in rows:
        jt = q.canonical_job_type(job_type)
        if jt not in totals:
            totals[jt] = {}
        totals[jt][status] = int(cnt)

    if not totals:
        print("No compute_jobs rows found in DB.")
        return

    col_w = max(len(k) for k in totals) + 2
    header = (
        f"{'job_type':<{col_w}}"
        f"{'routing':<20}"
        f"{'claimable':<12}"
        f"{'pending':>10}"
        f"{'claimed':>10}"
        f"{'succeeded':>12}"
        f"{'failed':>8}"
    )
    print(header)
    print("-" * len(header))

    unclaimed_worker_only: list[str] = []
    unclaimed_prefer_worker: list[str] = []
    total_stuck = 0

    for jt in sorted(totals.keys()):
        counts = totals[jt]
        pending = counts.get("pending", 0)
        claimed = counts.get("claimed", 0)
        succeeded = counts.get("succeeded", 0)
        failed = counts.get("failed", 0)
        routing = _routing_label(jt)
        claimable = worker_claim_enabled(jt)
        claimable_str = "YES" if claimable else "NO "

        print(
            f"{jt:<{col_w}}"
            f"{routing:<20}"
            f"{claimable_str:<12}"
            f"{pending:>10}"
            f"{claimed:>10}"
            f"{succeeded:>12}"
            f"{failed:>8}"
        )
        if pending > 0 and not claimable:
            total_stuck += pending
            if requires_worker(jt):
                unclaimed_worker_only.append(jt)
            else:
                unclaimed_prefer_worker.append(jt)

    print()
    print(f"Total stuck pending (not claimable): {total_stuck:,}")

    if not unclaimed_worker_only and not unclaimed_prefer_worker:
        print(
            "\n✓ All pending job types are claimable.\n"
            "  Possible causes for 0 claimed:\n"
            "  - Worker is rate-limited (compute_claim_min_interval_seconds)\n"
            "  - Worker's claims_paused_until is set in compute_workers table\n"
            "  - Worker is not sending the right job_types in the claim request\n"
            "  - task_pause_service has the type paused in Redis (bgjob:paused_tasks)\n"
        )
        return

    print("\n=== ROOT CAUSE ===\n")

    if unclaimed_prefer_worker:
        print(
            "PREFER_WORKER jobs are stuck because compute_offload_enabled=False\n"
            "(or the job type is not listed in compute_offload_job_types).\n"
            "\n"
            "These jobs were enqueued when offloading was enabled.\n"
            "Now they can't be claimed — they will sit here forever unless you:\n"
            "  a) Set compute_offload_enabled=True in .env  →  worker claims them\n"
            "  b) Run scripts/purge_stale_compute_jobs.py  →  purge stale ones\n"
            "\n"
            f"Affected types: {', '.join(unclaimed_prefer_worker)}\n"
        )

    if unclaimed_worker_only:
        print(
            "WORKER_ONLY jobs are stuck — these require the remote worker and\n"
            "have NO local fallback.  They will NOT execute without the worker.\n"
            "\n"
            "  Check:\n"
            "  - Is the ComputeWorker running and sending heartbeats?\n"
            "  - Does it include these job_types in the claim request?\n"
            "  - Is the worker suspended? Check compute_workers.suspended_until\n"
            "  - Is the worker's IP in its allowed_ip_cidrs?\n"
            "\n"
            f"Affected types: {', '.join(unclaimed_worker_only)}\n"
        )

    print(
        "NOTE: Do NOT delete WORKER_ONLY jobs without explicit intent.\n"
        "      PREFER_WORKER (SC catalog sync etc.) are safe to purge —\n"
        "      they will be re-enqueued automatically on the next sync cycle.\n"
        "      Run: poetry run python scripts/purge_stale_compute_jobs.py\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)
