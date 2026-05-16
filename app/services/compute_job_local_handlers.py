from __future__ import annotations

from typing import Any

from app.services import compute_queue_service as q
from app.services.compute_job_dispatcher import (
    LocalComputeHandler,
    LocalComputeJob,
)


async def _catalog_full(job: LocalComputeJob) -> dict[str, Any] | None:
    from app.services.artist_catalog_sync_worker import (
        run_sync_artist_catalog_local,
    )

    return await run_sync_artist_catalog_local(job)


async def _catalog_station(job: LocalComputeJob) -> dict[str, Any] | None:
    from app.services.artist_catalog_sync_worker import (
        run_sync_artist_similar_station_local,
    )

    return await run_sync_artist_similar_station_local(job)


async def _catalog_release(job: LocalComputeJob) -> dict[str, Any] | None:
    from app.services.artist_catalog_sync_worker import (
        run_sync_artist_release_local,
    )

    return await run_sync_artist_release_local(job)


_HANDLERS: dict[str, LocalComputeHandler] = {
    q.JOB_SC_ARTIST_CATALOG_SYNC: _catalog_full,
    q.JOB_SC_ARTIST_SIMILAR_STATION_SYNC: _catalog_station,
    q.JOB_SC_ARTIST_RELEASE_SYNC: _catalog_release,
}


def get_local_handler(job_type: str) -> LocalComputeHandler | None:
    return _HANDLERS.get(q.canonical_job_type(job_type))


__all__ = [
    "get_local_handler",
]
