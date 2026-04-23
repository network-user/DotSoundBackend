"""Print core Track columns for a given id (for ops / debugging).

Usage (from repo root)::

    poetry run python scripts/inspect_track.py 74

Requires DATABASE_URL and app deps (``poetry install``).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.db import (  # noqa: E402
    AsyncSessionLocal,
    dispose_engine,
)
from app.models.track import Track  # noqa: E402


async def _main(track_id: int) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Track).where(Track.id == track_id)
        )
        t = result.scalar_one_or_none()
    if t is None:
        print(f"Track id={track_id} not found")
        return 1
    print(f"id:              {t.id}")
    print(f"title:           {t.title!r}")
    print(f"artist:          {t.artist!r}")
    print(f"is_active:       {t.is_active}")
    print(f"source:          {t.source!r}")
    print(f"source_platform: {t.source_platform!r}")
    print(f"imported_from:   {t.imported_from!r}")
    print(f"file_key:        {t.file_key!r}")
    print(f"sc_url:          {t.sc_url!r}")
    print(f"duration_s:      {t.duration_seconds}")
    has_asr = bool(t.file_key) or bool(t.sc_url)
    print(
        f"asr_audio_resolvable: {has_asr}  "
        f"(lyrics_cascade: file_key or sc_url)"
    )
    await dispose_engine()
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Show Track row for ASR/lyrics debugging"
    )
    p.add_argument(
        "track_id",
        type=int,
        help="tracks.id, e.g. 74",
    )
    args = p.parse_args()
    raise SystemExit(asyncio.run(_main(args.track_id)))
