import asyncio
import os
import shutil
import tempfile

import structlog
from sqlalchemy import update

from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.track import Track

logger = structlog.stdlib.get_logger(__name__)


async def _update_video_status(
    track_id: int,
    status: str,
    video_key: str | None = None,
    thumbnail_key: str | None = None,
) -> None:
    async with AsyncSessionLocal() as session:
        values: dict[str, object] = {
            "video_processing_status": status,
        }
        if video_key is not None:
            values["video_key"] = video_key
        if thumbnail_key is not None:
            values["video_thumbnail_key"] = thumbnail_key
        await session.execute(
            update(Track)
            .where(Track.id == track_id)
            .values(**values)
        )
        await session.commit()


@broker.task
async def transcode_video(
    track_id: int,
    raw_key: str,
    original_filename: str,
) -> None:
    structlog.contextvars.bind_contextvars(
        track_id=track_id
    )
    logger.info("video_transcoding_started")

    tmp_dir = tempfile.mkdtemp()
    ext = os.path.splitext(original_filename)[1] or ".mp4"
    input_path = os.path.join(tmp_dir, f"input{ext}")
    output_path = os.path.join(tmp_dir, "output.mp4")
    thumb_path = os.path.join(tmp_dir, "thumb.jpg")

    try:
        raw_data, _, _, _ = (
            await s3.download_object_range(raw_key)
        )
        with open(input_path, "wb") as f:
            f.write(raw_data)

        transcode_cmd = [
            "ffmpeg", "-i", input_path,
            "-vf",
            "scale='min(720,iw)':'min(720,ih)'"
            ":force_original_aspect_ratio=decrease",
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-y", output_path,
        ]
        process = await asyncio.create_subprocess_exec(
            *transcode_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(
                "video_transcode_failed",
                returncode=process.returncode,
                stderr=stderr.decode()[:500],
            )
            await _update_video_status(
                track_id, "error"
            )
            return

        thumb_cmd = [
            "ffmpeg", "-i", output_path,
            "-ss", "1",
            "-frames:v", "1",
            "-q:v", "2",
            "-y", thumb_path,
        ]
        thumb_proc = await asyncio.create_subprocess_exec(
            *thumb_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await thumb_proc.communicate()

        with open(output_path, "rb") as f:
            video_data = f.read()

        video_key = f"videos/{track_id}/processed.mp4"
        await s3.upload_object(
            key=video_key,
            data=video_data,
            content_type="video/mp4",
        )

        thumbnail_key: str | None = None
        if os.path.exists(thumb_path):
            with open(thumb_path, "rb") as f:
                thumb_data = f.read()
            thumbnail_key = (
                f"videos/{track_id}/thumb.jpg"
            )
            await s3.upload_object(
                key=thumbnail_key,
                data=thumb_data,
                content_type="image/jpeg",
            )

        await _update_video_status(
            track_id,
            "active",
            video_key=video_key,
            thumbnail_key=thumbnail_key,
        )
        logger.info(
            "video_transcoding_completed",
            video_key=video_key,
        )

    except Exception:
        logger.exception("video_transcoding_error")
        await _update_video_status(
            track_id, "error"
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        try:
            await s3.delete_object(raw_key)
        except Exception:
            pass
