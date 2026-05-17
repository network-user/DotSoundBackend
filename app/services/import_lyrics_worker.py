"""Post-import lyrics orchestrator.

Enqueued at the end of a successful external-import job. Schedules
:meth:`LyricsService.enqueue_background_lyrics` per imported
track so catalog-only LyricsJob tiers run consistently with new
uploads. Pacing and proxy block circuit-breaking match the legacy
generator loop.
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
from app.services.lyrics_service import LyricsService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


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


async def _enqueue_to_global_queue(
    *,
    imported_items: list,
    repo: LyricsRepository,
    job_id: int,
) -> None:
    """Hand off all imported track ids to the shared lyrics
    queue. Skips tracks that already have lyrics in the DB so we
    don't re-fetch.
    """
    from app.services.lyrics_global_orchestrator import enqueue

    track_ids: list[int] = []
    for item in imported_items:
        track_id = item.get("track_id") if isinstance(item, dict) else None
        if isinstance(track_id, int):
            track_ids.append(track_id)
    already_have_lyrics = await repo.nonempty_plain_track_ids(track_ids)

    enqueued_total = 0
    skipped_total = 0
    for track_id in track_ids:
        if track_id in already_have_lyrics:
            skipped_total += 1
            continue
        try:
            await enqueue(track_id, with_sync=True)
            enqueued_total += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "import_lyrics_global_enqueue_failed",
                job_id=job_id,
                track_id=track_id,
                error=str(exc),
            )
    logger.info(
        "import_lyrics_handed_to_global_queue",
        job_id=job_id,
        enqueued=enqueued_total,
        skipped=skipped_total,
    )


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

    When ``settings.lyrics_global_orchestrator_enabled`` is True,
    pushes every imported track id onto the shared Redis queue
    and exits. The shared :func:`lyrics_global_orchestrator
    ._orchestrator_loop` then paces them across all jobs.
    """
    async with AsyncSessionLocal() as session:
        job = await session.get(ImportJob, job_id)
        if job is None:
            logger.warning("import_lyrics_skip_missing_job", job_id=job_id)
            return
        tracks_data = job.tracks_data or {}
        imported = tracks_data.get("imported") or []
        if not imported:
            logger.info("import_lyrics_nothing_to_do", job_id=job_id)
            return

        repo = LyricsRepository(session)
        logger.info(
            "import_lyrics_start",
            job_id=job_id,
            tracks=len(imported),
        )

        if settings.lyrics_global_orchestrator_enabled:
            await _enqueue_to_global_queue(
                imported_items=imported,
                repo=repo,
                job_id=job_id,
            )
            return

        consecutive_blocks = 0
        enqueued_total = 0
        skipped_total = 0

        candidate_track_ids: list[int] = []
        for item in imported:
            tid = item.get("track_id") if isinstance(item, dict) else None
            if isinstance(tid, int):
                candidate_track_ids.append(tid)
        already_have_lyrics = await repo.nonempty_plain_track_ids(
            candidate_track_ids
        )

        for idx, item in enumerate(imported):
            track_id = item.get("track_id") if isinstance(item, dict) else None
            if not isinstance(track_id, int):
                continue

            if track_id in already_have_lyrics:
                skipped_total += 1
                logger.debug(
                    "import_lyrics_skip_existing",
                    job_id=job_id,
                    track_id=track_id,
                )
                continue

            try:
                lyrics_svc = LyricsService(session)
                progress_id = await lyrics_svc.enqueue_background_lyrics(
                    track_id,
                    requested_by_user_id=None,
                    with_sync=True,
                    bypass_cache=False,
                )
                if not progress_id:
                    skipped_total += 1
                    logger.debug(
                        "import_lyrics_enqueue_skipped",
                        job_id=job_id,
                        track_id=track_id,
                    )
                else:
                    enqueued_total += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "import_lyrics_enqueue_failed",
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
                delay = _cooldown() if blocked else _pick_delay()
                await asyncio.sleep(delay)

        logger.info(
            "import_lyrics_done",
            job_id=job_id,
            enqueued=enqueued_total,
            skipped=skipped_total,
        )
