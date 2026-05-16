"""Taskiq worker for track info enrichment.

The actual provider is an opaque dependency from dotsound_private_core.
This module must not name specific external providers, APIs, or services.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from taskiq import TaskiqEvents, TaskiqState

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.repositories.track_info import TrackInfoRepository
from app.services import compute_queue_service as q
from app.services.compute_job_dispatcher import (
    LocalComputeJob,
    dispatch_compute_job,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_PROVIDER_TIMEOUT_SECONDS = 90.0


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _preload_track_info_provider(
    _state: TaskiqState,
) -> None:
    try:
        from dotsound_private_core.services.track_info_provider import (
            warmup_track_info_provider,
        )
    except Exception:
        logger.info("track_info_provider_warmup_unavailable")
        return

    try:
        await asyncio.to_thread(warmup_track_info_provider)
        logger.info("track_info_provider_warmup_done")
    except Exception:
        logger.exception("track_info_provider_warmup_failed")


async def fetch_track_info_local(job: LocalComputeJob) -> dict:
    import time

    track_id = int(job.target_id or job.payload.get("track_id") or 0)
    structlog.contextvars.bind_contextvars(track_id=track_id)
    logger.info("fetch_track_info_task_picked_up", track_id=track_id)
    t_start = time.monotonic()
    async with AsyncSessionLocal() as session:
        repo = TrackInfoRepository(session)

        from sqlalchemy import select

        from app.models.artist import Artist, TrackArtist
        from app.models.track import Track

        result = await session.execute(
            select(Track).where(Track.id == track_id)
        )
        track = result.scalar_one_or_none()
        if track is None:
            logger.warning("track_info_track_not_found", track_id=track_id)
            await repo.upsert(
                track_id, status="failed", content=None, fetched_at=None
            )
            await session.commit()
            return {"status": "not_found"}

        artist_name = track.artist or ""
        if not artist_name:
            result2 = await session.execute(
                select(Artist.name)
                .join(TrackArtist, TrackArtist.artist_id == Artist.id)
                .where(
                    TrackArtist.track_id == track_id,
                    TrackArtist.role == "primary",
                )
                .limit(1)
            )
            row = result2.first()
            if row:
                artist_name = row[0]

        try:
            from dotsound_private_core.services.track_info_provider import (
                fetch_track_info,
            )

            info = await asyncio.wait_for(
                asyncio.to_thread(
                    fetch_track_info,
                    title=track.title,
                    artist=artist_name,
                ),
                timeout=_PROVIDER_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.warning(
                "track_info_provider_timeout",
                track_id=track_id,
                timeout=_PROVIDER_TIMEOUT_SECONDS,
            )
            await repo.upsert(
                track_id,
                status="failed",
                content=None,
                fetched_at=datetime.now(UTC),
            )
            await session.commit()
            return {"status": "timeout"}
        except Exception:
            logger.exception("track_info_provider_error", track_id=track_id)
            await repo.upsert(
                track_id,
                status="failed",
                content=None,
                fetched_at=datetime.now(UTC),
            )
            await session.commit()
            return {"status": "error"}

        if info is None or info.status == "not_found":
            await repo.upsert(
                track_id,
                status="not_found",
                content=None,
                fetched_at=datetime.now(UTC),
            )
            await session.commit()
            logger.info("track_info_not_found", track_id=track_id)
            return {"status": "not_found"}

        content = (info.content or "")[:12_000]
        await repo.upsert(
            track_id,
            status="done",
            content=content,
            fetched_at=datetime.now(UTC),
        )
        await session.commit()
        logger.info(
            "track_info_done",
            track_id=track_id,
            elapsed_s=round(time.monotonic() - t_start, 2),
            content_len=len(content),
        )
        return {"status": "done"}


@broker.task
async def fetch_track_info_task(track_id: int) -> dict:
    async with AsyncSessionLocal() as session:
        dispatched = await dispatch_compute_job(
            session,
            job_type=q.JOB_TRACK_INFO_FETCH,
            target_kind=q.TARGET_KIND_TRACK,
            target_id=track_id,
            payload={"track_id": track_id},
            local_handler=fetch_track_info_local,
        )
        await session.commit()
    return dispatched.result or {"status": dispatched.status}
