import asyncio
import os
import tempfile
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core import s3
from app.core.db import AsyncSessionLocal
from app.models.track import Track

logger = structlog.stdlib.get_logger(__name__)


async def transcode_and_upload(
    track_id: int,
    raw_audio_data: bytes,
    original_filename: str,
) -> None:
    """
    Background task to transcode audio using FFmpeg and upload to S3.
    """
    structlog.contextvars.bind_contextvars(track_id=track_id)
    logger.info("transcoding_started")

    # Create temporary files
    # We use tempfile to safely handle disk I/O
    fd_in, temp_in_path = tempfile.mkstemp(suffix=os.path.splitext(original_filename)[1] or ".tmp")
    fd_out, temp_out_path = tempfile.mkstemp(suffix=".mp3")

    try:
        # Write raw bytes to input temp file
        with open(fd_in, "wb") as f_in:
            f_in.write(raw_audio_data)

        # Run FFmpeg to encode to MP3 192kbps
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", temp_in_path,
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            temp_out_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(
                "ffmpeg_failed",
                stderr=stderr.decode(errors="replace")[-500:],
            )
            await _update_track_status(track_id, "error", None, None)
            return

        # FFmpeg succeeded, read the output file
        with open(temp_out_path, "rb") as f_out:
            mp3_data = f_out.read()

        file_size = len(mp3_data)
        if file_size == 0:
            logger.error("ffmpeg_zero_bytes")
            await _update_track_status(track_id, "error", None, None)
            return

        # Upload MP3 to S3
        # Assuming we can get uploader_id from DB
        async with AsyncSessionLocal() as session:
            track = await session.get(Track, track_id)
            if not track:
                logger.error("track_not_found_in_db")
                return
            uploader_id = track.uploaded_by_id

        file_key = await s3.upload_audio(
            data=mp3_data,
            extension="mp3",
            content_type="audio/mpeg",
            user_id=uploader_id,
        )

        logger.info(
            "transcoding_complete",
            file_key=file_key,
            size_bytes=file_size,
        )

        # Update DB track
        await _update_track_status(track_id, "active", file_key, file_size)

    except Exception as e:
        logger.exception("transcoding_exception", error=str(e))
        await _update_track_status(track_id, "error", None, None)

    finally:
        # Cleanup temp files
        os.close(fd_out)
        if os.path.exists(temp_in_path):
            os.remove(temp_in_path)
        if os.path.exists(temp_out_path):
            os.remove(temp_out_path)


async def _update_track_status(
    track_id: int,
    status: str,
    file_key: str | None,
    file_size: int | None,
) -> None:
    async with AsyncSessionLocal() as session:
        try:
            track = await session.get(Track, track_id)
            if track:
                track.processing_status = status
                if file_key:
                    track.file_key = file_key
                if file_size is not None:
                    track.file_size_bytes = file_size
                await session.commit()
                logger.info("track_status_updated", status=status)
        except Exception as e:
            logger.error("failed_to_update_track_status", error=str(e))
            await session.rollback()
