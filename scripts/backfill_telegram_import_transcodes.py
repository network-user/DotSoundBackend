"""Queue playback repair for legacy Telegram-imported tracks.

Usage:
    poetry run python scripts/backfill_telegram_import_transcodes.py
    poetry run python scripts/backfill_telegram_import_transcodes.py --apply
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
from app.services.telegram_import_backfill_service import (  # noqa: E402
    TelegramImportBackfillService,
)


async def _main(*, limit: int, apply: bool) -> int:
    async with AsyncSessionLocal() as session:
        service = TelegramImportBackfillService(session)
        report = await service.run(limit=limit, dry_run=not apply)
        if apply:
            await session.commit()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    await dispose_engine()
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Find legacy Telegram imports without normalized playback "
            "assets and queue MP3/HLS repair."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of candidate tracks to inspect.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Queue repair tasks. Without this flag the script is dry-run.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_main(limit=args.limit, apply=args.apply)))
