import structlog

from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.track import Track
from app.services.cover_generator import generate_cover

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


@broker.task
async def generate_and_upload_cover(
    track_id: int,
) -> None:
    async with AsyncSessionLocal() as session:
        track = await session.get(Track, track_id)
        if not track:
            logger.warning(
                "cover_gen_skip_not_found",
                track_id=track_id,
            )
            return

        seed = (
            f"{track.title}:{track.id}"
            f":{track.created_at}"
        )
        png_bytes = generate_cover(seed)

        if track.cover_key:
            try:
                await s3.delete_object(track.cover_key)
            except Exception:
                logger.warning(
                    "cover_gen_old_delete_failed",
                    track_id=track_id,
                )

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
