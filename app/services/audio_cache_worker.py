"""Background task: download third-party audio → store in S3 CAS → link to track.

Status machine: None → "caching" → "cached" | "failed"
HLS-only streams are marked "failed" — they cannot be stored as a single blob.
"""

from __future__ import annotations

import structlog
import httpx

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.track import Track
from app.services.audio_blob_service import AudioBlobService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/aac": "aac",
    "audio/x-m4a": "m4a",
    "audio/flac": "flac",
    "application/octet-stream": "mp3",
}


async def _resolve_stream(track: Track) -> tuple[str, str]:
    """Return (stream_url, protocol) for a third-party track."""
    from app.services.soundcloud_service import SoundCloudService
    from app.services.bandcamp_service import BandcampService

    platform = track.source_platform

    if platform == "soundcloud" or (not platform and track.sc_url):
        if not track.sc_url:
            raise ValueError("SC track missing sc_url")
        async with AsyncSessionLocal() as s:
            svc = SoundCloudService(settings.sc_client_id, s)
            return await svc.get_stream_info(track.sc_url, use_cache=True)

    if platform == "bandcamp":
        if not track.source_url:
            raise ValueError("Bandcamp track missing source_url")
        async with AsyncSessionLocal() as s:
            svc = BandcampService(s)
            return await svc.get_stream_info(track.source_url)

    raise ValueError(f"Unsupported platform for audio cache: {platform!r}")


async def _download_bytes(url: str) -> tuple[bytes, str]:
    """Download audio from *url* and return (data, content_type)."""
    async with httpx.AsyncClient(
        timeout=settings.audio_cache_download_timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": settings.outbound_user_agent},
    ) as client:
        r = await client.get(url)
        r.raise_for_status()
        ct = r.headers.get("content-type", "audio/mpeg").split(";")[0].strip()
        return r.content, ct


@broker.task
async def cache_track_audio(track_id: int) -> None:
    if not settings.audio_caching_enabled:
        return

    async with AsyncSessionLocal() as session:
        track = await session.get(Track, track_id)
        if track is None:
            return
        if track.audio_cache_status in ("cached", "caching"):
            return
        if track.access_mode != "third_party_stream":
            return
        if track.blob_id is not None:
            # Already has a blob — just mark cached if not already
            if track.audio_cache_status != "cached":
                track.audio_cache_status = "cached"
                await session.commit()
            return

        try:
            stream_url, protocol = await _resolve_stream(track)
        except Exception as exc:
            logger.warning(
                "audio_cache_resolve_failed",
                track_id=track_id,
                error=str(exc),
            )
            track.audio_cache_status = "failed"
            await session.commit()
            return

        if protocol == "hls":
            logger.info("audio_cache_hls_skip", track_id=track_id)
            track.audio_cache_status = "failed"
            await session.commit()
            return

        track.audio_cache_status = "caching"
        await session.commit()

    # Download outside the session to avoid holding a DB connection.
    try:
        data, content_type = await _download_bytes(stream_url)
    except Exception as exc:
        logger.warning(
            "audio_cache_download_failed",
            track_id=track_id,
            error=str(exc),
        )
        async with AsyncSessionLocal() as session:
            t = await session.get(Track, track_id)
            if t:
                t.audio_cache_status = "failed"
                await session.commit()
        return

    if len(data) > settings.audio_cache_max_file_bytes:
        logger.info(
            "audio_cache_oversized",
            track_id=track_id,
            bytes=len(data),
        )
        async with AsyncSessionLocal() as session:
            t = await session.get(Track, track_id)
            if t:
                t.audio_cache_status = "failed"
                await session.commit()
        return

    extension = _CONTENT_TYPE_TO_EXT.get(content_type, "mp3")

    async with AsyncSessionLocal() as session:
        t = await session.get(Track, track_id)
        if t is None or t.audio_cache_status != "caching":
            return
        blob_svc = AudioBlobService(session)
        blob, _ = await blob_svc.get_or_create_from_bytes(
            data, extension, content_type
        )
        await blob_svc.attach_playback_blob(t, blob)
        t.audio_cache_status = "cached"
        await session.commit()
        logger.info(
            "audio_cache_stored",
            track_id=track_id,
            blob_id=blob.id,
            bytes=len(data),
        )
