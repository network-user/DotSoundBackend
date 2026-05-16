from __future__ import annotations

import contextlib
from typing import Any

import structlog
from dotsound_private_core.services.sc_anti_block_policy import (
    SC_CATALOG_SYNC_MIN_INTERVAL_SECONDS,
    should_backpressure,
)

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.repositories.artist_catalog import ArtistCatalogRepository
from app.services import artist_catalog_sync_progress as acsp
from app.services import compute_queue_service as q
from app.services.artist_catalog_sync_service import ArtistCatalogSyncService
from app.services.compute_job_dispatcher import (
    LocalComputeHandler,
    LocalComputeJob,
    dispatch_compute_job,
)
from app.services.soundcloud_service import SoundCloudTrackUnavailable

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_STATION_BATCH_SIZE = 20

_IDEMPOTENCY_KEY_FULL = "sc:catalog_sync:full:{artist_id}"
_IDEMPOTENCY_KEY_STATION = "sc:catalog_sync:station:{artist_id}"
_IDEMPOTENCY_KEY_RELEASE = "sc:catalog_sync:release:{artist_id}:{album_id}"
_IDEMPOTENCY_LOCK_SECONDS = SC_CATALOG_SYNC_MIN_INTERVAL_SECONDS


async def _try_claim_idempotency(key: str) -> bool:
    """SET NX EX -- True if we just claimed the lock and may proceed."""
    try:
        from app.core.redis import get_redis_client

        redis = get_redis_client()
        ok = await redis.set(
            key,
            "1",
            ex=_IDEMPOTENCY_LOCK_SECONDS,
            nx=True,
        )
        return bool(ok)
    except Exception as exc:
        logger.warning(
            "sc_catalog_sync_idempotency_redis_failed",
            key=key,
            error=str(exc)[:200],
        )
        return True  # fail-open: do the work rather than silently skip


async def _pending_task_queue_length() -> int:
    """Approximate length of the default Taskiq queue in Redis.

    Used by cron sweeps as a backpressure signal so we do not stuff
    the queue with thousands of catalog syncs faster than the worker
    can drain. Returns ``-1`` if Redis is unreachable so the caller
    fails open (and the sweep still runs).
    """
    try:
        from app.core.redis import get_redis_client

        redis = get_redis_client()
        return int(await redis.llen("taskiq"))
    except Exception:
        return -1


def _payload_int(
    job: LocalComputeJob,
    key: str,
    *,
    default: int = 0,
) -> int:
    raw = job.payload.get(key)
    if raw is None and key == "artist_id":
        raw = job.target_id
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


async def run_sync_artist_catalog_local(
    job: LocalComputeJob,
) -> dict[str, Any]:
    artist_id = _payload_int(job, "artist_id")
    try:
        async with AsyncSessionLocal() as session:
            svc = ArtistCatalogSyncService(session)
            result = await svc.sync_full_artist(artist_id)
        await acsp.set_success(
            artist_id,
            mode="full",
            soundcloud_album_id=None,
            detail=result,
        )
        return result
    except SoundCloudTrackUnavailable as exc:
        logger.info(
            "sc_catalog_sync_track_unavailable",
            artist_id=artist_id,
            track_ref=str(exc.track_ref),
            reason=exc.reason,
        )
        await acsp.set_success(
            artist_id,
            mode="full",
            soundcloud_album_id=None,
            detail={
                "status": "partial_skipped_dead_track",
                "skipped_track_ref": str(exc.track_ref),
            },
        )
        return {
            "status": "partial_skipped_dead_track",
            "artist_id": artist_id,
            "skipped_track_ref": str(exc.track_ref),
        }
    except Exception as exc:
        await acsp.set_error(
            artist_id,
            mode="full",
            soundcloud_album_id=None,
            message=repr(exc),
        )
        raise


async def run_sync_artist_similar_station_local(
    job: LocalComputeJob,
) -> dict[str, Any]:
    artist_id = _payload_int(job, "artist_id")
    force = bool(job.payload.get("force"))
    try:
        async with AsyncSessionLocal() as session:
            svc = ArtistCatalogSyncService(session)
            result = await svc.sync_artist_similar_station(
                artist_id,
                skip_background_lyrics=bool(
                    job.payload.get("skip_background_lyrics")
                ),
                force=force,
            )
        detail = {
            **({"forced": True} if force else {}),
            "station_synced": result.get("status") == "ok",
            **result,
        }
        await acsp.set_success(
            artist_id,
            mode="station",
            soundcloud_album_id=None,
            detail=detail,
        )
        return detail
    except SoundCloudTrackUnavailable as exc:
        logger.info(
            "sc_station_sync_track_unavailable",
            artist_id=artist_id,
            track_ref=str(exc.track_ref),
            reason=exc.reason,
        )
        detail = {
            "status": "partial_skipped_dead_track",
            "artist_id": artist_id,
            "skipped_track_ref": str(exc.track_ref),
            **({"forced": True} if force else {}),
        }
        await acsp.set_success(
            artist_id,
            mode="station",
            soundcloud_album_id=None,
            detail=detail,
        )
        return detail
    except Exception as exc:
        await acsp.set_error(
            artist_id,
            mode="station",
            soundcloud_album_id=None,
            message=repr(exc),
        )
        raise


async def _dispatch_catalog_job(
    *,
    artist_id: int,
    job_type: str,
    mode: str,
    payload: dict[str, Any],
    local_handler: LocalComputeHandler,
    soundcloud_album_id: int | None = None,
    force_local: bool = False,
) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        dispatched = await dispatch_compute_job(
            session,
            job_type=job_type,
            target_kind=q.TARGET_KIND_ARTIST,
            target_id=artist_id,
            payload=payload,
            local_handler=local_handler,
            force_local=force_local,
        )
        await session.commit()
    if dispatched.status == "queued":
        detail = {
            "status": "queued_compute",
            "phase": "queued_compute",
            "job_id": dispatched.job_id,
        }
        await acsp.set_running(
            artist_id,
            mode=mode,
            soundcloud_album_id=soundcloud_album_id,
            detail=detail,
        )
        return detail
    return dispatched.result or {"status": "ok"}


@broker.task
async def sync_artist_catalog_task(artist_id: int) -> dict[str, Any]:
    """Full catalog sync for a single artist.

    Wraps a Redis lock so duplicate enqueues (cron sweep + admin
    re-enqueue + retry) collapse to a single run per hour. Catches
    :class:`SoundCloudTrackUnavailable` cleanly so dead/private
    tracks do not dead-letter the whole catalog sync.
    """
    key = _IDEMPOTENCY_KEY_FULL.format(artist_id=artist_id)
    if not await _try_claim_idempotency(key):
        logger.info(
            "sc_catalog_sync_skipped_idempotent",
            artist_id=artist_id,
            mode="full",
        )
        return {"status": "skipped_idempotent", "artist_id": artist_id}
    return await _dispatch_catalog_job(
        artist_id=artist_id,
        job_type=q.JOB_SC_ARTIST_CATALOG_SYNC,
        mode="full",
        payload={"artist_id": artist_id},
        local_handler=run_sync_artist_catalog_local,
    )


@broker.task
async def sync_artist_similar_station_task(
    artist_id: int,
) -> dict[str, Any]:
    key = _IDEMPOTENCY_KEY_STATION.format(artist_id=artist_id)
    if not await _try_claim_idempotency(key):
        logger.info(
            "sc_catalog_sync_skipped_idempotent",
            artist_id=artist_id,
            mode="station",
        )
        return {"status": "skipped_idempotent", "artist_id": artist_id}
    return await _dispatch_catalog_job(
        artist_id=artist_id,
        job_type=q.JOB_SC_ARTIST_SIMILAR_STATION_SYNC,
        mode="station",
        payload={"artist_id": artist_id},
        local_handler=run_sync_artist_similar_station_local,
    )


@broker.task
async def force_sync_artist_similar_station_task(
    artist_id: int,
    *,
    skip_background_lyrics: bool = False,
) -> dict[str, Any]:
    return await _dispatch_catalog_job(
        artist_id=artist_id,
        job_type=q.JOB_SC_ARTIST_SIMILAR_STATION_SYNC,
        mode="station",
        payload={
            "artist_id": artist_id,
            "force": True,
            "skip_background_lyrics": skip_background_lyrics,
        },
        local_handler=run_sync_artist_similar_station_local,
        force_local=True,
    )


async def run_sync_artist_release_local(
    job: LocalComputeJob,
) -> dict[str, Any]:
    artist_id = _payload_int(job, "artist_id")
    soundcloud_album_id = _payload_int(job, "soundcloud_album_id")
    try:
        async with AsyncSessionLocal() as session:
            svc = ArtistCatalogSyncService(session)
            result = await svc.sync_single_release(
                artist_id,
                soundcloud_album_id,
            )
        await acsp.set_success(
            artist_id,
            mode="release",
            soundcloud_album_id=soundcloud_album_id,
            detail=result,
        )
        return result
    except SoundCloudTrackUnavailable as exc:
        logger.info(
            "sc_release_sync_track_unavailable",
            artist_id=artist_id,
            soundcloud_album_id=soundcloud_album_id,
            track_ref=str(exc.track_ref),
            reason=exc.reason,
        )
        await acsp.set_success(
            artist_id,
            mode="release",
            soundcloud_album_id=soundcloud_album_id,
            detail={
                "status": "partial_skipped_dead_track",
                "skipped_track_ref": str(exc.track_ref),
            },
        )
        return {
            "status": "partial_skipped_dead_track",
            "artist_id": artist_id,
            "soundcloud_album_id": soundcloud_album_id,
        }
    except Exception as exc:
        await acsp.set_error(
            artist_id,
            mode="release",
            soundcloud_album_id=soundcloud_album_id,
            message=repr(exc),
        )
        raise


@broker.task
async def sync_stale_stations_batch_task() -> dict[str, Any]:
    """Weekly sweep: enqueue station sync for stale artist stations.

    Skips when the Taskiq queue is already long enough that adding
    more work would only make the backlog worse. The threshold is
    defined in :mod:`dotsound_private_core.services.sc_anti_block_policy`
    so backend and worker share the same notion of "too full".
    """
    from dotsound_private_core.services.catalog_sync_policy import (
        STATION_SWEEP_MAX_ARTISTS_PER_RUN,
    )

    from app.config import settings

    queue_len = await _pending_task_queue_length()
    if queue_len >= 0 and should_backpressure(queue_len):
        logger.warning(
            "sc_sweep_skipped_backpressure",
            mode="station",
            queue_length=queue_len,
        )
        return {
            "status": "skipped_backpressure",
            "queue_length": queue_len,
        }

    async with AsyncSessionLocal() as session:
        repo = ArtistCatalogRepository(session)
        artist_ids = await repo.find_stale_station_artist_ids(
            settings.artist_station_stale_threshold_days,
            limit=STATION_SWEEP_MAX_ARTISTS_PER_RUN,
        )

    enqueued = 0
    skipped_idempotent = 0
    for i in range(0, len(artist_ids), _STATION_BATCH_SIZE):
        batch = artist_ids[i : i + _STATION_BATCH_SIZE]
        for artist_id in batch:
            key = _IDEMPOTENCY_KEY_STATION.format(artist_id=artist_id)
            from app.core.redis import get_redis_client

            with contextlib.suppress(Exception):
                redis = get_redis_client()
                if await redis.exists(key):
                    skipped_idempotent += 1
                    continue
            await sync_artist_similar_station_task.kiq(artist_id)
            enqueued += 1

    logger.info(
        "station_stale_sweep_complete",
        enqueued=enqueued,
        skipped_idempotent=skipped_idempotent,
        total_stale=len(artist_ids),
        cap=STATION_SWEEP_MAX_ARTISTS_PER_RUN,
    )
    return {
        "enqueued": enqueued,
        "skipped_idempotent": skipped_idempotent,
    }


_CATALOG_FULL_BATCH_SIZE = 10
_CATALOG_FULL_SWEEP_LIMIT = 50


@broker.task
async def sync_stale_catalogs_batch_task() -> dict[str, Any]:
    """Bi-weekly sweep: enqueue full catalog sync for artists with
    stale or missing non-station catalog."""
    from app.config import settings

    queue_len = await _pending_task_queue_length()
    if queue_len >= 0 and should_backpressure(queue_len):
        logger.warning(
            "sc_sweep_skipped_backpressure",
            mode="catalog",
            queue_length=queue_len,
        )
        return {
            "status": "skipped_backpressure",
            "queue_length": queue_len,
        }

    async with AsyncSessionLocal() as session:
        repo = ArtistCatalogRepository(session)
        artist_ids = await repo.find_stale_full_catalog_artist_ids(
            settings.artist_catalog_full_sync_stale_threshold_days,
            limit=_CATALOG_FULL_SWEEP_LIMIT,
        )

    enqueued = 0
    skipped_idempotent = 0
    for i in range(0, len(artist_ids), _CATALOG_FULL_BATCH_SIZE):
        batch = artist_ids[i : i + _CATALOG_FULL_BATCH_SIZE]
        for artist_id in batch:
            key = _IDEMPOTENCY_KEY_FULL.format(artist_id=artist_id)
            from app.core.redis import get_redis_client

            with contextlib.suppress(Exception):
                redis = get_redis_client()
                if await redis.exists(key):
                    skipped_idempotent += 1
                    continue
            await sync_artist_catalog_task.kiq(artist_id)
            enqueued += 1

    logger.info(
        "catalog_stale_sweep_complete",
        enqueued=enqueued,
        skipped_idempotent=skipped_idempotent,
        total_stale=len(artist_ids),
    )
    return {
        "enqueued": enqueued,
        "skipped_idempotent": skipped_idempotent,
    }


@broker.task
async def sync_artist_catalog_release_task(
    artist_id: int,
    soundcloud_album_id: int,
) -> dict[str, Any]:
    key = _IDEMPOTENCY_KEY_RELEASE.format(
        artist_id=artist_id,
        album_id=soundcloud_album_id,
    )
    if not await _try_claim_idempotency(key):
        logger.info(
            "sc_catalog_sync_skipped_idempotent",
            artist_id=artist_id,
            mode="release",
            soundcloud_album_id=soundcloud_album_id,
        )
        return {
            "status": "skipped_idempotent",
            "artist_id": artist_id,
            "soundcloud_album_id": soundcloud_album_id,
        }
    return await _dispatch_catalog_job(
        artist_id=artist_id,
        job_type=q.JOB_SC_ARTIST_RELEASE_SYNC,
        mode="release",
        payload={
            "artist_id": artist_id,
            "soundcloud_album_id": soundcloud_album_id,
        },
        local_handler=run_sync_artist_release_local,
        soundcloud_album_id=soundcloud_album_id,
    )
