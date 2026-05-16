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


async def _artist_enrichment(job: LocalComputeJob) -> dict[str, Any] | None:
    from app.services.artist_enrichment_worker import enrich_artist_local

    return await enrich_artist_local(job)


async def _track_info(job: LocalComputeJob) -> dict[str, Any] | None:
    from app.services.track_info_worker import fetch_track_info_local

    return await fetch_track_info_local(job)


async def _external_import_scan(job: LocalComputeJob) -> dict[str, Any] | None:
    from app.services.external_import_worker import (
        process_external_import_job_local,
    )

    return await process_external_import_job_local(job)


async def _track_waveform(job: LocalComputeJob) -> dict[str, Any] | None:
    from app.services.waveform_worker import generate_waveform_local

    return await generate_waveform_local(job)


async def _track_transcoding(job: LocalComputeJob) -> dict[str, Any] | None:
    from app.services.transcoding import transcode_and_upload_local

    return await transcode_and_upload_local(job)


async def _track_snippet(job: LocalComputeJob) -> dict[str, Any] | None:
    from app.services.snippet_worker import transcode_snippet_local

    return await transcode_snippet_local(job)


async def _track_cover(job: LocalComputeJob) -> dict[str, Any] | None:
    from app.services.cover_worker import generate_and_upload_cover_local

    return await generate_and_upload_cover_local(job)


_HANDLERS: dict[str, LocalComputeHandler] = {
    q.JOB_SC_ARTIST_CATALOG_SYNC: _catalog_full,
    q.JOB_SC_ARTIST_SIMILAR_STATION_SYNC: _catalog_station,
    q.JOB_SC_ARTIST_RELEASE_SYNC: _catalog_release,
    q.JOB_ARTIST_ENRICHMENT: _artist_enrichment,
    q.JOB_TRACK_INFO_FETCH: _track_info,
    q.JOB_EXTERNAL_IMPORT_SCAN: _external_import_scan,
    q.JOB_TRACK_TRANSCODING: _track_transcoding,
    q.JOB_TRACK_WAVEFORM: _track_waveform,
    q.JOB_TRACK_SNIPPET: _track_snippet,
    q.JOB_TRACK_COVER_PROCESSING: _track_cover,
}


def get_local_handler(job_type: str) -> LocalComputeHandler | None:
    return _HANDLERS.get(q.canonical_job_type(job_type))


__all__ = [
    "get_local_handler",
]
