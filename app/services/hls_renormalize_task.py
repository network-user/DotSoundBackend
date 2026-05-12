from __future__ import annotations

import structlog
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.track import Track

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_DEFAULT_BATCH = 50


@broker.task
async def renormalize_track_hls_task(
    track_id: int,
    file_key: str,
) -> None:
    from app.services.transcoding import transcode_hls_only

    await transcode_hls_only(track_id, file_key)


@broker.task
async def hls_renormalize_batch_task(
    offset: int = 0,
    batch_size: int = _DEFAULT_BATCH,
) -> dict:
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Track.id, Track.file_key)
            .where(
                Track.processing_status == "active",
                Track.file_key.is_not(None),
            )
            .order_by(Track.id.asc())
            .offset(offset)
            .limit(batch_size)
        )
        rows = (await session.execute(stmt)).all()

    enqueued = 0
    for track_id, file_key in rows:
        await renormalize_track_hls_task.kiq(
            track_id=track_id,
            file_key=file_key,
        )
        enqueued += 1

    done = len(rows) < batch_size
    logger.info(
        "hls_renormalize_batch_dispatched",
        offset=offset,
        enqueued=enqueued,
        done=done,
    )
    return {"offset": offset, "enqueued": enqueued, "done": done}
