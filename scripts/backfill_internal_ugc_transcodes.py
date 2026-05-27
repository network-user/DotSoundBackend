"""Queue playback normalization for internal-stream UGC tracks.

Usage:
    poetry run python scripts/backfill_internal_ugc_transcodes.py
    poetry run python scripts/backfill_internal_ugc_transcodes.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.db import AsyncSessionLocal, dispose_engine  # noqa: E402
from app.services.ugc_playback_normalize_service import (  # noqa: E402
    UgcPlaybackNormalizeService,
)


async def _main(*, limit: int, apply: bool) -> int:
    async with AsyncSessionLocal() as session:
        service = UgcPlaybackNormalizeService(session)
        report = await service.run(
            limit=limit,
            dry_run=not apply,
            urgent=False,
            force_retry=apply,
        )
        if apply:
            await session.commit()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    await dispose_engine()
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Find internal-stream UGC tracks missing MP3/HLS and "
            "queue background normalization"
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="enqueue repair jobs (default: dry run)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="max tracks per run",
    )
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(_main(limit=args.limit, apply=args.apply))
    )
