from __future__ import annotations

import structlog

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


def _should() -> bool:
    return bool(
        settings.elasticsearch_enabled
        and (settings.elasticsearch_url or "").strip()
    )


async def schedule_reindex_track(track_id: int) -> None:
    if not _should():
        return
    try:
        from app.services import search_index_worker

        await search_index_worker.reindex_track_task.kiq(track_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "reindex_track_enqueue_failed",
            track_id=track_id,
            error=str(exc),
        )


async def schedule_reindex_artist(artist_id: int) -> None:
    if not _should():
        return
    try:
        from app.services import search_index_worker

        await search_index_worker.reindex_artist_task.kiq(
            artist_id
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "reindex_artist_enqueue_failed",
            artist_id=artist_id,
            error=str(exc),
        )


async def schedule_delete_track(track_id: int) -> None:
    if not _should():
        return
    try:
        from app.services import search_index_worker

        await search_index_worker.delete_track_es_task.kiq(
            track_id
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "delete_track_es_enqueue_failed",
            track_id=track_id,
            error=str(exc),
        )
