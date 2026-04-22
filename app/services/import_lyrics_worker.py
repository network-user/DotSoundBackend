"""Post-import lyrics orchestrator.

Enqueued as a fire-and-forget Taskiq task at the end of a
successful external-import job. Walks through the imported
tracks and spawns a :func:`generate_lyrics_task` per track with
a randomised pause in between, plus a circuit-breaker that
extends the pause (or bails out entirely) when the upstream
proxy reports a block-like failure.

The orchestrator itself never calls the provider directly — it
only enqueues the existing ``generate_lyrics_task``, which
handles caching, DB persistence and the actual lyrics cascade.
This keeps ASR out of this file's hot path completely.
"""
from __future__ import annotations

import asyncio
import random

import structlog

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.import_job import ImportJob
from app.repositories.lyrics import LyricsRepository
from app.services.lyrics_worker import generate_lyrics_task

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


# Consecutive block signals tolerated before the orchestrator
# gives up on the rest of the job. Captcha'd proxies don't usually
# recover within a single cooldown, so burning time on more retries
# is pointless — better to bail out and let the user re-run later.
MAX_CONSECUTIVE_BLOCKS = 5

# Substrings (lowercase) in :func:`proxy_pool.last_error` output
# that mean "the upstream blocked us". Matching is opaque to the
# upstream's actual endpoint shape so backend never needs to know
# what a "captcha" looks like structurally.
_BLOCK_MARKERS = ("captcha", "pool_exhaust", "exhausted")


def _is_block_signal(message: str | None) -> bool:
    if not message:
        return False
    lowered = message.lower()
    return any(marker in lowered for marker in _BLOCK_MARKERS)


def _peek_last_error() -> str | None:
    """Indirect read of the PrivateCore proxy-pool error state.

    Imported locally so the backend module-load graph stays clean
    of optional dependencies.
    """
    try:
        from dotsound_private_core.services import (  # noqa: PLC0415
            proxy_pool,
        )
    except ImportError:
        return None
    try:
        return proxy_pool.last_error()
    except Exception:  # noqa: BLE001
        return None


def _pick_delay() -> float:
    lo = float(settings.yandex_music_import_lyrics_delay_min_seconds)
    hi = float(settings.yandex_music_import_lyrics_delay_max_seconds)
    if hi < lo:
        hi = lo
    return random.uniform(lo, hi)


def _cooldown() -> float:
    return float(settings.yandex_music_import_lyrics_cooldown_seconds)


@broker.task
async def process_import_lyrics_task(job_id: int) -> None:
    """Orchestrate paced lyrics generation for an import job.

    Fire-and-forget: enqueued from ``process_external_import_job``
    once the job itself is marked done. The function loads the
    imported-track ids from ``ImportJob.tracks_data["imported"]``
    and kiq's :func:`generate_lyrics_task` for each track that
    doesn't already have lyrics in the DB.

    Never raises; all failures are logged and the loop moves on
    to the next track unless the circuit-breaker trips.
    """
    async with AsyncSessionLocal() as session:
        job = await session.get(ImportJob, job_id)
        if job is None:
            logger.warning(
                "import_lyrics_skip_missing_job", job_id=job_id
            )
            return
        tracks_data = job.tracks_data or {}
        imported = tracks_data.get("imported") or []
        if not imported:
            logger.info(
                "import_lyrics_nothing_to_do", job_id=job_id
            )
            return

        repo = LyricsRepository(session)
        logger.info(
            "import_lyrics_start",
            job_id=job_id,
            tracks=len(imported),
        )

        consecutive_blocks = 0
        enqueued_total = 0
        skipped_total = 0

        for idx, item in enumerate(imported):
            track_id = item.get("track_id") if isinstance(
                item, dict
            ) else None
            if not isinstance(track_id, int):
                continue

            existing = await repo.get_by_track_id(track_id)
            if existing is not None:
                skipped_total += 1
                logger.debug(
                    "import_lyrics_skip_existing",
                    job_id=job_id,
                    track_id=track_id,
                )
                continue

            try:
                await generate_lyrics_task.kiq(
                    track_id,
                    with_sync=True,
                    progress_id="",
                )
                enqueued_total += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "import_lyrics_kiq_failed",
                    job_id=job_id,
                    track_id=track_id,
                    error=str(exc),
                )
                continue

            # Inspect upstream pool state AFTER enqueueing so the
            # lyrics worker has had a chance to touch the network
            # on tracks processed earlier in this job (previous
            # iterations). This deliberately uses the pool's
            # internal counter — it's the only cross-worker
            # signal we have without a dedicated queue probe.
            last_error = _peek_last_error()
            blocked = _is_block_signal(last_error)
            if blocked:
                consecutive_blocks += 1
                logger.warning(
                    "import_lyrics_block_signal",
                    job_id=job_id,
                    track_id=track_id,
                    last_error=last_error,
                    consecutive=consecutive_blocks,
                )
            else:
                consecutive_blocks = 0

            if consecutive_blocks >= MAX_CONSECUTIVE_BLOCKS:
                logger.warning(
                    "import_lyrics_early_exit",
                    job_id=job_id,
                    enqueued=enqueued_total,
                    skipped=skipped_total,
                    remaining=len(imported) - idx - 1,
                )
                return

            # Don't sleep after the very last track — nothing to
            # pace against. Sleep happens BEFORE the next iteration.
            if idx < len(imported) - 1:
                delay = (
                    _cooldown() if blocked else _pick_delay()
                )
                await asyncio.sleep(delay)

        logger.info(
            "import_lyrics_done",
            job_id=job_id,
            enqueued=enqueued_total,
            skipped=skipped_total,
        )
