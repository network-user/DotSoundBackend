"""Run the lyrics audio-compute lease reaper once (no Taskiq).

Frees ``running`` jobs whose ``deadline_at`` is in the past: either
fails over in the cascade or marks the row terminal. Same logic as
``reap_expired_jobs_task`` / ``app.tasks.audio_compute_reaper``.

Usage (from repo root)::

    poetry run python scripts/reap_lyrics_lease.py

Use when the Taskiq schedule is not running (e.g. local dev) and you
do not want to run raw SQL. Prefer
``POST /api/v1/admin/audio-compute/operations/reap-expired-leases``
in production (admin token).
"""

from __future__ import annotations

import asyncio

from app.tasks.audio_compute_reaper import reap_once


async def _main() -> None:
    n = await reap_once()
    print(f"reap_lyrics_lease: handled {n} job(s)")


if __name__ == "__main__":
    asyncio.run(_main())
