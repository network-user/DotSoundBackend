import asyncio
import os
import shutil
import tempfile
from contextlib import suppress
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.track import Track

if TYPE_CHECKING:
    from app.models.image_blob import ImageBlob
    from app.models.video_blob import VideoBlob

logger = structlog.stdlib.get_logger(__name__)


async def _update_video_status(
    track_id: int,
    status: str,
    video_key: str | None = None,
    thumbnail_key: str | None = None,
    expected_status: str | None = None,
) -> bool:
    async with AsyncSessionLocal() as session:
        values: dict[str, object] = {
            "video_processing_status": status,
        }
        if video_key is not None:
            values["video_key"] = video_key
        if thumbnail_key is not None:
            values["video_thumbnail_key"] = thumbnail_key
        stmt = update(Track).where(Track.id == track_id)
        if expected_status is not None:
            stmt = stmt.where(
                Track.video_processing_status == expected_status
            )
        result = await session.execute(
            stmt.values(**values)
        )
        await session.commit()
        updated = result.rowcount > 0
        if not updated and expected_status is not None:
            logger.info(
                "video_transcoding_stale_status_skipped",
                target_status=status,
                expected_status=expected_status,
            )
        return updated


async def _is_current_video_task(
    track_id: int,
    expected_status: str | None,
) -> bool:
    if expected_status is None:
        return True
    async with AsyncSessionLocal() as session:
        status = await session.scalar(
            select(Track.video_processing_status).where(
                Track.id == track_id
            )
        )
    if status == expected_status:
        return True
    logger.info(
        "video_transcoding_stale_task_skipped",
        expected_status=expected_status,
        actual_status=status,
    )
    return False


async def _delete_created_video_artifacts(
    session: AsyncSession,
    video_blob: "VideoBlob",
    video_created: bool,
    thumb_blob: "ImageBlob | None",
    thumb_created: bool,
) -> None:
    if video_created:
        with suppress(Exception):
            await s3.delete_object(video_blob.s3_key)
        await session.delete(video_blob)
    if thumb_blob is not None and thumb_created:
        with suppress(Exception):
            await s3.delete_object(thumb_blob.s3_key)
        await session.delete(thumb_blob)


async def _attach_video_if_current(
    track_id: int,
    expected_status: str | None,
    video_data: bytes,
    thumb_data: bytes | None,
) -> tuple[str, str | None] | None:
    async with AsyncSessionLocal() as cas_session:
        from app.services.image_blob_service import ImageBlobService
        from app.services.video_blob_service import VideoBlobService

        video_svc = VideoBlobService(cas_session)
        video_blob, video_created = (
            await video_svc.get_or_create_from_bytes(
                video_data, "mp4", "video/mp4"
            )
        )
        video_key = video_blob.s3_key

        thumb_blob = None
        thumb_created = False
        thumbnail_key: str | None = None
        if thumb_data is not None:
            img_svc = ImageBlobService(cas_session)
            thumb_blob, thumb_created = (
                await img_svc.get_or_create_from_bytes(
                    thumb_data, "jpg", "image/jpeg"
                )
            )
            thumbnail_key = thumb_blob.s3_key

        values: dict[str, object] = {
            "video_processing_status": "active",
            "video_key": video_key,
            "video_blob_id": video_blob.id,
            "video_blob_ref_freed": False,
        }
        if thumbnail_key is not None:
            values["video_thumbnail_key"] = thumbnail_key

        stmt = update(Track).where(Track.id == track_id)
        if expected_status is not None:
            stmt = stmt.where(
                Track.video_processing_status == expected_status
            )
        result = await cas_session.execute(
            stmt.values(**values)
        )
        if result.rowcount == 0:
            logger.info(
                "video_transcoding_stale_attach_skipped",
                expected_status=expected_status,
            )
            await _delete_created_video_artifacts(
                cas_session,
                video_blob,
                video_created,
                thumb_blob,
                thumb_created,
            )
            await cas_session.commit()
            return None

        video_blob.ref_count = video_blob.ref_count + 1
        if thumb_blob is not None:
            thumb_blob.ref_count = thumb_blob.ref_count + 1
            video_blob.thumbnail_blob_id = thumb_blob.id
        await cas_session.commit()
        return video_key, thumbnail_key


@broker.task
async def transcode_video(
    track_id: int,
    raw_key: str,
    original_filename: str,
    expected_status: str | None = None,
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
                track_id,
                "error_transcode",
                expected_status=expected_status,
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

        thumb_data: bytes | None = None
        if os.path.exists(thumb_path):
            with open(thumb_path, "rb") as f:
                thumb_data = f.read()

        if not await _is_current_video_task(
            track_id, expected_status
        ):
            return

        attached = await _attach_video_if_current(
            track_id,
            expected_status,
            video_data,
            thumb_data,
        )
        if attached is None:
            return
        video_key, thumbnail_key = attached

        logger.info(
            "video_transcoding_completed",
            video_key=video_key,
            thumbnail_key=thumbnail_key,
        )

    except Exception:
        logger.exception("video_transcoding_error")
        await _update_video_status(
            track_id,
            "error_internal",
            expected_status=expected_status,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        with suppress(Exception):
            await s3.delete_object(raw_key)
