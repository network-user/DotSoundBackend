import contextlib
import time

import structlog

from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.track import Track
from app.services import compute_queue_service as q
from app.services.compute_job_dispatcher import (
    LocalComputeJob,
    dispatch_compute_job,
)
from app.services.cover_generator import generate_cover

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def generate_and_upload_cover_local(
    job: LocalComputeJob,
) -> dict:
    track_id = int(job.target_id or job.payload.get("track_id") or 0)
    async with AsyncSessionLocal() as session:
        track = await session.get(Track, track_id)
        if not track:
            logger.warning(
                "cover_gen_skip_not_found",
                track_id=track_id,
            )
            return {"status": "not_found"}

        old_cover_key = track.cover_key

        seed = f"{track.title}:{track.id}" f":{time.time()}"
        png_bytes = generate_cover(seed)

        cover_key = await s3.upload_cover(
            data=png_bytes,
            content_type="image/png",
            user_id=track.uploaded_by_id,
        )

        track.cover_key = cover_key
        await session.commit()

        logger.info(
            "cover_generated",
            track_id=track_id,
            cover_key=cover_key,
        )

        if old_cover_key and old_cover_key != cover_key:
            with contextlib.suppress(Exception):
                await s3.delete_object(old_cover_key)
    return {"status": "ok", "cover_key": cover_key}


@broker.task
async def generate_and_upload_cover(
    track_id: int,
) -> None:
    async with AsyncSessionLocal() as session:
        await dispatch_compute_job(
            session,
            job_type=q.JOB_TRACK_COVER_PROCESSING,
            target_kind=q.TARGET_KIND_TRACK,
            target_id=track_id,
            payload={"track_id": track_id},
            local_handler=generate_and_upload_cover_local,
        )
        await session.commit()
