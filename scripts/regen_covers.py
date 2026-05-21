"""Re-encode legacy track covers under the current cover defaults.

Runs ``cover_regen_worker.regen_covers_sweep_task`` in-process (no
Taskiq broker required) so an operator can drain the cover backlog
under direct observation.

Runbook:
- Take a DB backup or at least a MinIO snapshot before running in prod.
- Pass ``--loop`` to keep paging until the cursor exhausts.

Environment:
- ``DOTSOUND_ALLOW_COVER_REGEN=1`` must be set (safety guard).
- ``COVER_REGEN_ENABLED=true`` must be set so the worker tasks are
  actually allowed to mutate data.

Usage:
    DOTSOUND_ALLOW_COVER_REGEN=1 COVER_REGEN_ENABLED=true \\
        poetry run python scripts/regen_covers.py [--loop]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import structlog

from app.services.cover_regen_worker import (
    regen_covers_gc_task,
    regen_covers_sweep_task,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _run_once() -> dict[str, object]:
    return await regen_covers_sweep_task()


async def _run_loop() -> None:
    total_processed = 0
    total_saved = 0
    batches = 0
    while True:
        summary = await regen_covers_sweep_task()
        batches += 1
        total_processed += int(summary.get("processed", 0))
        total_saved += int(summary.get("bytes_saved", 0))
        logger.info(
            "regen_covers_loop_batch",
            batch=batches,
            **summary,
        )
        if summary.get("exhausted"):
            break
    logger.info(
        "regen_covers_loop_done",
        batches=batches,
        total_processed=total_processed,
        total_bytes_saved=total_saved,
    )


async def _run_gc() -> dict[str, object]:
    return await regen_covers_gc_task()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--loop",
        action="store_true",
        help="keep paging batches until the cursor reports exhaustion",
    )
    parser.add_argument(
        "--gc",
        action="store_true",
        help="drain the delete-scheduled queue instead of sweeping",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    if os.environ.get("DOTSOUND_ALLOW_COVER_REGEN") != "1":
        logger.error(
            "regen_covers_disabled",
            hint=("set DOTSOUND_ALLOW_COVER_REGEN=1 to confirm intent"),
        )
        sys.exit(2)
    if args.gc:
        summary = await _run_gc()
        logger.info("regen_covers_gc_done", **summary)
        return
    if args.loop:
        await _run_loop()
        return
    summary = await _run_once()
    logger.info("regen_covers_single_done", **summary)


if __name__ == "__main__":
    asyncio.run(_main())
