from __future__ import annotations

import asyncio
import os
import re
import secrets
import tempfile
from contextlib import suppress

import structlog
from dotsound_private_core.services.upload_policy import (
    MAX_VIDEO_BYTES,
    should_fast_attach_track_video,
)
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.models.track import Track
from app.services.file_validator import validate_video_async
from app.services.image_blob_service import ImageBlobService
from app.services.video_blob_service import VideoBlobService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_ALLOWED_VIDEO_CONTENT_TYPES = frozenset(
    {"video/mp4", "video/webm", "video/quicktime"}
)


def normalize_video_upload_content_type(
    content_type: str | None,
) -> str | None:
    base = (content_type or "").split(";")[0].strip().lower()
    if not base or base == "application/octet-stream":
        return None
    if base in ("video/quicktime", "application/mp4"):
        return "video/mp4"
    if base in ("video/mp4", "video/webm"):
        return base
    if base in _ALLOWED_VIDEO_CONTENT_TYPES:
        return "video/mp4"
    return base


async def _extract_thumbnail_bytes(
    video_data: bytes,
    extension: str,
) -> bytes | None:
    tmp_dir = tempfile.mkdtemp()
    input_path = os.path.join(
        tmp_dir, f"input{extension or '.mp4'}"
    )
    thumb_path = os.path.join(tmp_dir, "thumb.jpg")

    def _run() -> bytes | None:
        try:
            with open(input_path, "wb") as handle:
                handle.write(video_data)
            import subprocess

            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-i",
                    input_path,
                    "-ss",
                    "0.5",
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    "-y",
                    thumb_path,
                ],
                capture_output=True,
                timeout=30,
                check=False,
            )
            if proc.returncode != 0 or not os.path.exists(thumb_path):
                return None
            with open(thumb_path, "rb") as thumb_handle:
                return thumb_handle.read()
        except Exception:
            return None
        finally:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)

    return await asyncio.to_thread(_run)


async def _clear_existing_track_video(track: Track) -> None:
    if not track.video_key:
        return
    with suppress(Exception):
        await s3.delete_object(track.video_key)
    track.video_key = None
    track.video_thumbnail_key = None


async def _fast_attach_track_video(
    session: AsyncSession,
    track: Track,
    data: bytes,
    content_type: str,
    detected_mime: str,
) -> None:
    await _clear_existing_track_video(track)
    video_svc = VideoBlobService(session)
    blob, _ = await video_svc.get_or_create_from_bytes(
        data, "mp4", content_type or detected_mime
    )
    thumb_data = await _extract_thumbnail_bytes(data, ".mp4")
    if thumb_data:
        img_svc = ImageBlobService(session)
        thumb_blob, _ = await img_svc.get_or_create_from_bytes(
            thumb_data, "jpg", "image/jpeg"
        )
        await video_svc.set_thumbnail(blob, thumb_blob)
        track.video_thumbnail_key = thumb_blob.s3_key
    await video_svc.attach_to_track(track, blob)
    track.video_processing_status = "active"
    await session.flush()
    logger.info(
        "track_video_fast_attach_completed",
        track_id=track.id,
        video_key=track.video_key,
    )


async def _queue_track_video_transcode(
    track: Track,
    data: bytes,
    content_type: str,
    filename: str | None,
) -> None:
    await _clear_existing_track_video(track)
    safe_name = re.sub(
        r"[^\w.\-]", "_", filename or "video"
    )[:100]
    raw_key = f"temp/video/{track.id}_{safe_name}"
    await s3.upload_object(
        key=raw_key, data=data, content_type=content_type
    )
    processing_status = f"processing:{secrets.token_hex(4)}"
    track.video_processing_status = processing_status
    from app.services.video_transcoding import transcode_video

    await transcode_video.kiq(
        track_id=track.id,
        raw_key=raw_key,
        original_filename=filename or "video.mp4",
        expected_status=processing_status,
    )


async def upload_track_video_bytes(
    session: AsyncSession,
    track: Track,
    data: bytes,
    content_type: str | None,
    filename: str | None,
) -> None:
    if len(data) > MAX_VIDEO_BYTES:
        limit_mb = MAX_VIDEO_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Video exceeds {limit_mb} MB limit",
        )

    normalized = normalize_video_upload_content_type(
        content_type
    )
    detected = await validate_video_async(data, filename)
    if normalized is None:
        if detected == "video/mp4":
            normalized = "video/mp4"
        elif detected == "video/webm":
            normalized = "video/webm"
        else:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Video must be MP4 or WebM",
            )
    elif normalized not in {"video/mp4", "video/webm"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Video must be MP4 or WebM",
        )

    if should_fast_attach_track_video(detected, len(data)):
        await _fast_attach_track_video(
            session,
            track,
            data,
            normalized,
            detected,
        )
        return

    await _queue_track_video_transcode(
        track,
        data,
        normalized,
        filename,
    )
    await session.flush()
