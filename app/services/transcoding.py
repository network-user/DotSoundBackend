import asyncio
import contextlib
import json
import os
import re
import shutil
import tempfile

import structlog
from dotsound_private_core.services.playback_streaming_policy import (
    DEFAULT_HLS_HI_BITRATE_KBPS,
    DEFAULT_HLS_LO_BITRATE_KBPS,
    DEFAULT_HLS_SEGMENT_SECONDS,
    DEFAULT_PROGRESSIVE_MP3_BITRATE_KBPS,
    LATEST_BUNDLE_VERSION,
    build_master_playlist,
)

from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker  # Добавлено
from app.models.track import Track
from app.services import compute_queue_service as q
from app.services.audio_blob_service import AudioBlobService
from app.services.compute_job_dispatcher import (
    LocalComputeJob,
    dispatch_compute_job,
)

logger = structlog.stdlib.get_logger(__name__)

_HLS_TIME = DEFAULT_HLS_SEGMENT_SECONDS
_HI_BITRATE = f"{DEFAULT_HLS_HI_BITRATE_KBPS}k"
_LO_BITRATE = f"{DEFAULT_HLS_LO_BITRATE_KBPS}k"
_MP3_BITRATE = f"{DEFAULT_PROGRESSIVE_MP3_BITRATE_KBPS}k"
_LOUDNORM_FILTER = "loudnorm=I=-14:TP=-1:LRA=11"
_FFMPEG_TIMEOUT_SEC = 600
_LOUDNORM_STATS_RE = re.compile(r'\{\s*"input_i".*?\}', re.DOTALL)

_MASTER_PLAYLIST = build_master_playlist()
_BUNDLE_VERSION = LATEST_BUNDLE_VERSION


async def transcode_and_upload_local(
    job: LocalComputeJob,
) -> dict | None:
    """Background task: transcode to MP3 192k + HLS 128k/64k, upload all.

    When ``source_sha256`` is provided the resulting AudioBlob is tagged
    with it and the HLS bundle is written to a content-addressed prefix
    so that later uploads of the same source can skip transcoding entirely.
    Any other Track rows that claimed the same source while this transcode
    was running are reconciled at the end.
    """
    track_id = int(job.target_id or job.payload.get("track_id") or 0)
    raw_key = str(job.payload.get("raw_key") or "")
    original_filename = str(
        job.payload.get("original_filename") or "input.audio"
    )
    source_raw = job.payload.get("source_sha256")
    source_sha256 = source_raw if isinstance(source_raw, str) else None
    structlog.contextvars.bind_contextvars(track_id=track_id)
    logger.info("transcoding_started", source_sha256=source_sha256)

    if not raw_key:
        await _update_track_status(track_id, "error", None, None)
        return {"status": "error", "error": "missing_raw_key"}

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
            "ffmpeg",
            "-y",
            "-i",
            temp_in_path,
            "-filter_complex",
            f"[0:a:0]{_LOUDNORM_FILTER}[norm]",
            # Output 1: MP3 for range streaming fallback
            "-map",
            "[norm]",
            "-c:a",
            "libmp3lame",
            "-b:a",
            _MP3_BITRATE,
            "-vn",
            temp_mp3_path,
            # Output 2: HLS hi quality
            "-map",
            "[norm]",
            "-c:a",
            "aac",
            "-b:a",
            _HI_BITRATE,
            "-vn",
            "-hls_time",
            str(_HLS_TIME),
            "-hls_list_size",
            "0",
            "-hls_flags",
            "independent_segments",
            "-hls_segment_filename",
            f"{hi_dir}/%03d.ts",
            f"{hi_dir}/playlist.m3u8",
            # Output 3: HLS lo quality (bad connection / save-data)
            "-map",
            "[norm]",
            "-c:a",
            "aac",
            "-b:a",
            _LO_BITRATE,
            "-vn",
            "-hls_time",
            str(_HLS_TIME),
            "-hls_list_size",
            "0",
            "-hls_flags",
            "independent_segments",
            "-hls_segment_filename",
            f"{lo_dir}/%03d.ts",
            f"{lo_dir}/playlist.m3u8",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=_FFMPEG_TIMEOUT_SEC,
            )
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            logger.error("ffmpeg_timeout", track_id=track_id)
            await _update_track_status(track_id, "error", None, None)
            return

        if process.returncode != 0:
            logger.error(
                "ffmpeg_failed",
                stderr=stderr.decode(errors="replace")[-500:],
            )
            await _update_track_status(track_id, "error", None, None)
            return

        stats = _parse_loudnorm_stats(stderr)
        if stats:
            logger.info("ffmpeg_loudnorm_stats", **stats)

        with open(temp_mp3_path, "rb") as f:
            mp3_data = f.read()

        if len(mp3_data) == 0:
            logger.error("ffmpeg_zero_bytes")
            await _update_track_status(track_id, "error", None, None)
            return

        # Upload HLS segments and playlists. When we know the source
        # hash we write to a CAS prefix so the bundle can be reused by
        # later uploads of the same source.
        manifest_key_uploaded = await _upload_hls(
            track_id, hi_dir, lo_dir, source_sha256
        )
        bundle_ok = await _verify_hls_bundle(
            track_id, manifest_key_uploaded
        )
        manifest_key: str | None = (
            manifest_key_uploaded if bundle_ok else None
        )
        if not bundle_ok:
            logger.warning(
                "hls_bundle_verify_failed_skip_link",
                track_id=track_id,
                manifest_key=manifest_key_uploaded,
            )

        # CAS MP3 blob: shared across users and imports when bytes match
        async with AsyncSessionLocal() as session:
            svc = AudioBlobService(session)
            track = await session.get(Track, track_id)
            if not track:
                await _update_track_status(track_id, "error", None, None)
                return
            ab, _ = await svc.get_or_create_from_bytes(
                mp3_data, "mp3", "audio/mpeg"
            )
            if source_sha256:
                await svc.claim_source(blob=ab, source_sha256=source_sha256)
            if manifest_key:
                await svc.set_hls_manifest_key(
                    blob=ab, hls_manifest_key=manifest_key
                )
            # If the track was previously linked to a different blob (e.g.
            # an imported track that was temporarily attached to the raw OGG
            # blob while waiting for transcoding), release the old ref first
            # so ref-counts stay accurate and the new MP3 blob can be linked.
            if track.blob_id is not None and track.blob_id != ab.id:
                await svc.try_release_for_track(track)
                track.blob_id = None
                track.blob_ref_freed = False
            await svc.attach_playback_blob(track, ab)
            track.processing_status = "active"
            track.file_size_bytes = len(mp3_data)
            track.hls_manifest_key = manifest_key
            track.hls_segment_seconds = _HLS_TIME
            track.hls_bundle_version = _BUNDLE_VERSION
            file_key_log = track.file_key
            reconciled = 0
            if source_sha256:
                reconciled = await svc.attach_pending_tracks(
                    source_sha256=source_sha256, blob=ab
                )
            await session.commit()
            if reconciled:
                logger.info(
                    "transcoding_reconciled_pending_tracks",
                    source_sha256=source_sha256,
                    reconciled=reconciled,
                )
            logger.info(
                "transcoding_complete",
                file_key=file_key_log,
                manifest_key=manifest_key,
                mp3_size=len(mp3_data),
            )
            from app.services.search_index_notify import (
                schedule_reindex_track,
            )
            from app.services.waveform_worker import (
                generate_waveform_task,
            )

            if track_id:
                await schedule_reindex_track(track_id)
                await generate_waveform_task.kiq(track_id)

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


@broker.task  # Превращаем в фоновую задачу воркера
async def transcode_and_upload(
    track_id: int,
    raw_key: str,  # Теперь принимаем ключ в S3 вместо байтов
    original_filename: str,
    source_sha256: str | None = None,
) -> None:
    async with AsyncSessionLocal() as session:
        await dispatch_compute_job(
            session,
            job_type=q.JOB_TRACK_TRANSCODING,
            target_kind=q.TARGET_KIND_TRACK,
            target_id=track_id,
            payload={
                "track_id": track_id,
                "raw_key": raw_key,
                "original_filename": original_filename,
                "source_sha256": source_sha256,
            },
            local_handler=transcode_and_upload_local,
        )
        await session.commit()


async def transcode_hls_only(
    track_id: int,
    file_key: str,
    source_sha256: str | None = None,
) -> None:
    """Re-transcode an existing MP3 track to HLS only (for batch migration).

    When ``source_sha256`` is supplied the bundle lands under a CAS
    prefix so multiple tracks sharing the same source converge on
    one set of segments and the migration cost amortises across the
    catalogue.
    """
    structlog.contextvars.bind_contextvars(track_id=track_id)
    logger.info(
        "hls_transcode_started",
        bundle_version=_BUNDLE_VERSION,
        segment_seconds=_HLS_TIME,
    )

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
            "ffmpeg",
            "-y",
            "-i",
            temp_in_path,
            "-filter_complex",
            f"[0:a:0]{_LOUDNORM_FILTER}[norm]",
            "-map",
            "[norm]",
            "-c:a",
            "aac",
            "-b:a",
            _HI_BITRATE,
            "-vn",
            "-hls_time",
            str(_HLS_TIME),
            "-hls_list_size",
            "0",
            "-hls_flags",
            "independent_segments",
            "-hls_segment_filename",
            f"{hi_dir}/%03d.ts",
            f"{hi_dir}/playlist.m3u8",
            "-map",
            "[norm]",
            "-c:a",
            "aac",
            "-b:a",
            _LO_BITRATE,
            "-vn",
            "-hls_time",
            str(_HLS_TIME),
            "-hls_list_size",
            "0",
            "-hls_flags",
            "independent_segments",
            "-hls_segment_filename",
            f"{lo_dir}/%03d.ts",
            f"{lo_dir}/playlist.m3u8",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=_FFMPEG_TIMEOUT_SEC,
            )
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            logger.error("ffmpeg_hls_timeout", track_id=track_id)
            return

        if process.returncode != 0:
            logger.error(
                "ffmpeg_hls_failed",
                stderr=stderr.decode(errors="replace")[-500:],
            )
            return

        stats = _parse_loudnorm_stats(stderr)
        if stats:
            logger.info("ffmpeg_loudnorm_stats", **stats)

        manifest_key = await _upload_hls(
            track_id, hi_dir, lo_dir, source_sha256
        )
        if not await _verify_hls_bundle(track_id, manifest_key):
            logger.error(
                "hls_transcode_bundle_invalid",
                manifest_key=manifest_key,
            )
            return

        async with AsyncSessionLocal() as session:
            track = await session.get(Track, track_id)
            if track:
                track.hls_manifest_key = manifest_key
                track.hls_segment_seconds = _HLS_TIME
                track.hls_bundle_version = _BUNDLE_VERSION
                await session.commit()
                logger.info(
                    "hls_transcode_complete",
                    manifest_key=manifest_key,
                    bundle_version=_BUNDLE_VERSION,
                )

    except Exception:
        logger.exception("hls_transcode_exception", track_id=track_id)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


async def _upload_hls(
    track_id: int,
    hi_dir: str,
    lo_dir: str,
    source_sha256: str | None = None,
) -> str:
    """Upload HLS segments + playlists, return master manifest key.

    When ``source_sha256`` is supplied, the bundle is written under a
    content-addressed prefix (``hls-blobs/{xx}/{sha}/...``) and the upload
    is skipped entirely if the master playlist already exists -- meaning
    a previous transcode of the same source has already produced it.
    Without ``source_sha256`` we fall back to the legacy per-track prefix.
    """
    if source_sha256:
        prefix = s3.build_cas_hls_prefix(
            source_sha256, bundle_version=_BUNDLE_VERSION
        )
        manifest_key = s3.build_cas_hls_master_key(
            source_sha256, bundle_version=_BUNDLE_VERSION
        )
        if await s3.object_exists(manifest_key):
            logger.info(
                "hls_cas_reused",
                manifest_key=manifest_key,
                source_sha256=source_sha256,
                bundle_version=_BUNDLE_VERSION,
            )
            return manifest_key
    else:
        prefix = f"hls/{track_id}"
        manifest_key = f"{prefix}/master.m3u8"

    for variant, local_dir in (
        ("hi", hi_dir),
        ("lo", lo_dir),
    ):
        for fname in sorted(os.listdir(local_dir)):
            full_path = os.path.join(local_dir, fname)
            data = await asyncio.to_thread(_read_file_bytes, full_path)
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

    await s3.upload_object(
        key=manifest_key,
        data=_MASTER_PLAYLIST.encode(),
        content_type="application/vnd.apple.mpegurl",
    )
    return manifest_key


async def _verify_hls_bundle(
    track_id: int,
    manifest_key: str,
) -> bool:
    """Sanity-check that the bundle we just uploaded is actually
    playable. If any of the master/variant/first-segment objects are
    missing we treat the bundle as broken so the Track row stays
    HLS-less and the frontend gracefully falls back to progressive
    playback instead of hanging on a 15 s startup timeout on every
    track switch (the long-standing "UGC stuck on buffering" bug).
    """
    prefix = manifest_key[: -len("/master.m3u8")] if manifest_key.endswith(
        "/master.m3u8"
    ) else f"hls/{track_id}"
    required = [
        manifest_key,
        f"{prefix}/hi/playlist.m3u8",
        f"{prefix}/lo/playlist.m3u8",
        f"{prefix}/hi/000.ts",
        f"{prefix}/lo/000.ts",
    ]
    for key in required:
        try:
            ok = await s3.object_exists(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "hls_bundle_verify_storage_error",
                track_id=track_id,
                key=key,
                error=str(exc),
            )
            return False
        if not ok:
            logger.warning(
                "hls_bundle_verify_missing",
                track_id=track_id,
                key=key,
            )
            return False
    return True


def _parse_loudnorm_stats(stderr: bytes) -> dict | None:
    m = _LOUDNORM_STATS_RE.search(stderr.decode(errors="replace"))
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


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
                from app.services.search_index_notify import (
                    schedule_reindex_track,
                )

                if track_id:
                    await schedule_reindex_track(track_id)
        except Exception:
            logger.exception("failed_to_update_track_status")
            await session.rollback()
