import asyncio
import os
import shutil
import tempfile

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker  # Добавлено
from app.models.track import Track

logger = structlog.stdlib.get_logger(__name__)

_HLS_TIME = 10
_HI_BITRATE = "128k"
_LO_BITRATE = "64k"

_MASTER_PLAYLIST = (
    "#EXTM3U\n"
    "#EXT-X-VERSION:3\n"
    '#EXT-X-STREAM-INF:BANDWIDTH=128000,CODECS="mp4a.40.2"\n'
    "hi/playlist.m3u8\n"
    '#EXT-X-STREAM-INF:BANDWIDTH=64000,CODECS="mp4a.40.2"\n'
    "lo/playlist.m3u8\n"
)


@broker.task  # Превращаем в фоновую задачу воркера
async def transcode_and_upload(
    track_id: int,
    raw_key: str,  # Теперь принимаем ключ в S3 вместо байтов
    original_filename: str,
) -> None:
    """Background task: transcode to MP3 192k + HLS 128k/64k, upload all."""
    structlog.contextvars.bind_contextvars(track_id=track_id)
    logger.info("transcoding_started")

    tmp_dir = tempfile.mkdtemp()
    ext = os.path.splitext(original_filename)[1] or ".tmp"
    temp_in_path = os.path.join(tmp_dir, f"input{ext}")
    temp_mp3_path = os.path.join(tmp_dir, "output.mp3")
    hi_dir = os.path.join(tmp_dir, "hi")
    lo_dir = os.path.join(tmp_dir, "lo")
    os.makedirs(hi_dir)
    os.makedirs(lo_dir)

    try:
        # Скачиваем оригинальный файл из временного хранилища S3
        raw_audio_data = await s3.download_object(raw_key)

        with open(temp_in_path, "wb") as f:
            f.write(raw_audio_data)

        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", temp_in_path,
            # Output 1: MP3 192k for range streaming fallback
            "-map", "0:a:0", "-c:a", "libmp3lame", "-b:a", "192k",
            "-vn", temp_mp3_path,
            # Output 2: HLS 128k (high quality)
            "-map", "0:a:0", "-c:a", "aac", "-b:a", _HI_BITRATE,
            "-vn", "-hls_time", str(_HLS_TIME), "-hls_list_size", "0",
            "-hls_segment_filename", f"{hi_dir}/%03d.ts",
            f"{hi_dir}/playlist.m3u8",
            # Output 3: HLS 64k (low quality / bad connection)
            "-map", "0:a:0", "-c:a", "aac", "-b:a", _LO_BITRATE,
            "-vn", "-hls_time", str(_HLS_TIME), "-hls_list_size", "0",
            "-hls_segment_filename", f"{lo_dir}/%03d.ts",
            f"{lo_dir}/playlist.m3u8",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(
                "ffmpeg_failed",
                stderr=stderr.decode(errors="replace")[-500:],
            )
            await _update_track_status(track_id, "error", None, None)
            return

        with open(temp_mp3_path, "rb") as f:
            mp3_data = f.read()

        if len(mp3_data) == 0:
            logger.error("ffmpeg_zero_bytes")
            await _update_track_status(track_id, "error", None, None)
            return

        # Upload MP3 (used as range-streaming fallback)
        async with AsyncSessionLocal() as session:
            track = await session.get(Track, track_id)
            uploader_id = track.uploaded_by_id if track else None

        file_key = await s3.upload_audio(
            data=mp3_data,
            extension="mp3",
            content_type="audio/mpeg",
            user_id=uploader_id,
        )

        # Upload HLS segments and playlists
        manifest_key = await _upload_hls(track_id, hi_dir, lo_dir)

        logger.info(
            "transcoding_complete",
            file_key=file_key,
            manifest_key=manifest_key,
            mp3_size=len(mp3_data),
        )

        await _update_track_status(
            track_id,
            "active",
            file_key,
            len(mp3_data),
            hls_manifest_key=manifest_key,
        )

    except Exception:
        logger.exception("transcoding_exception", track_id=track_id)
        await _update_track_status(track_id, "error", None, None)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        # Удаляем временный исходный файл из S3 после обработки
        try:
            await s3.delete_object(raw_key)
        except Exception:
            logger.warning("failed_to_delete_raw_temp_file", raw_key=raw_key)


async def transcode_hls_only(
    track_id: int, file_key: str
) -> None:
    """Re-transcode an existing MP3 track to HLS only (for batch migration)."""
    structlog.contextvars.bind_contextvars(track_id=track_id)
    logger.info("hls_transcode_started")

    tmp_dir = tempfile.mkdtemp()
    temp_in_path = os.path.join(tmp_dir, "input.mp3")
    hi_dir = os.path.join(tmp_dir, "hi")
    lo_dir = os.path.join(tmp_dir, "lo")
    os.makedirs(hi_dir)
    os.makedirs(lo_dir)

    try:
        mp3_data = await s3.download_object(file_key)
        with open(temp_in_path, "wb") as f:
            f.write(mp3_data)

        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", temp_in_path,
            "-map", "0:a:0", "-c:a", "aac", "-b:a", _HI_BITRATE,
            "-vn", "-hls_time", str(_HLS_TIME), "-hls_list_size", "0",
            "-hls_segment_filename", f"{hi_dir}/%03d.ts",
            f"{hi_dir}/playlist.m3u8",
            "-map", "0:a:0", "-c:a", "aac", "-b:a", _LO_BITRATE,
            "-vn", "-hls_time", str(_HLS_TIME), "-hls_list_size", "0",
            "-hls_segment_filename", f"{lo_dir}/%03d.ts",
            f"{lo_dir}/playlist.m3u8",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(
                "ffmpeg_hls_failed",
                stderr=stderr.decode(errors="replace")[-500:],
            )
            return

        manifest_key = await _upload_hls(track_id, hi_dir, lo_dir)

        async with AsyncSessionLocal() as session:
            track = await session.get(Track, track_id)
            if track:
                track.hls_manifest_key = manifest_key
                await session.commit()
                logger.info(
                    "hls_transcode_complete",
                    manifest_key=manifest_key,
                )

    except Exception:
        logger.exception("hls_transcode_exception", track_id=track_id)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def _upload_hls(
    track_id: int, hi_dir: str, lo_dir: str
) -> str:
    """Upload HLS segments + playlists, return master manifest key."""
    prefix = f"hls/{track_id}"

    for variant, local_dir in (("hi", hi_dir), ("lo", lo_dir)):
        for fname in sorted(os.listdir(local_dir)):
            data = open(os.path.join(local_dir, fname), "rb").read()
            ctype = (
                "application/vnd.apple.mpegurl"
                if fname.endswith(".m3u8")
                else "video/MP2T"
            )
            await s3.upload_object(
                key=f"{prefix}/{variant}/{fname}",
                data=data,
                content_type=ctype,
            )

    manifest_key = f"{prefix}/master.m3u8"
    await s3.upload_object(
        key=manifest_key,
        data=_MASTER_PLAYLIST.encode(),
        content_type="application/vnd.apple.mpegurl",
    )
    return manifest_key


async def _update_track_status(
    track_id: int,
    status: str,
    file_key: str | None,
    file_size: int | None,
    hls_manifest_key: str | None = None,
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
                if hls_manifest_key:
                    track.hls_manifest_key = hls_manifest_key
                await session.commit()
                logger.info("track_status_updated", status=status)
        except Exception:
            logger.exception("failed_to_update_track_status")
            await session.rollback()
