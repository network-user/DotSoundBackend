from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from taskiq import TaskiqEvents, TaskiqState

from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.config import settings
from app.models.track import Track
from app.repositories.lyrics import LyricsRepository

logger = structlog.stdlib.get_logger(__name__)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _preload_lyrics_assets(_state: TaskiqState) -> None:
    """Preload heavy assets used by the lyrics provider.

    Runs once per worker process. Heavy internal assets are
    materialised in local cache here so that the first user
    request doesn't pay the one-off latency.
    """
    from dotsound_private_core.services.lyrics_provider import (
        warmup_lyrics_provider,
    )

    logger.info("lyrics_assets_preload_start")
    await asyncio.to_thread(warmup_lyrics_provider)
    logger.info("lyrics_assets_preload_done")


async def _fetch_audio_to_file(
    track: Track,
    tmp_dir: str,
    session,  # AsyncSession
) -> str | None:
    """Download track audio to a temp file.

    Handles both internal (S3) and SoundCloud tracks transparently.
    Returns local file path, or None if audio is unavailable.
    """
    path = os.path.join(tmp_dir, "audio.mp3")

    if track.file_key:
        data = await s3.download_object(track.file_key)
        with open(path, "wb") as f:
            f.write(data)
        return path

    if getattr(track, "sc_url", None):
        try:
            import httpx
            from app.services.soundcloud_service import SoundCloudService

            sc = SoundCloudService(settings.sc_client_id, session)
            stream_url, protocol = await sc.get_stream_info(track.sc_url)

            if protocol != "progressive":
                logger.info(
                    "sc_audio_skip_hls",
                    protocol=protocol,
                    track_id=track.id,
                )
                return None

            async with httpx.AsyncClient(
                timeout=60, follow_redirects=True
            ) as client:
                resp = await client.get(stream_url)
                resp.raise_for_status()
                with open(path, "wb") as f:
                    f.write(resp.content)

            return path
        except Exception:
            logger.exception(
                "sc_audio_download_failed", track_id=track.id
            )
            return None

    return None


PROGRESS_KEY_PREFIX = "lyrics:progress:"
CANCEL_KEY_PREFIX = "lyrics:cancel:"
_PROGRESS_TTL = 600

# Allow-list of stage labels that may cross the backend↔frontend boundary.
# Any provider stage that falls outside this set is collapsed to "processing"
# so internal implementation details can't leak via the progress channel.
_PUBLIC_STAGES: frozenset[str] = frozenset(
    {
        "searching",
        "downloading_audio",
        "processing",
        "saving",
        "error",
        "cancelled",
    }
)

_STAGE_LABELS: dict[str, str] = {
    "searching": "looking up lyrics in sources",
    "downloading_audio": "downloading audio track",
    "processing": "audio-based provider processing (may take minutes)",
    "saving": "persisting results",
    "error": "error occurred",
    "cancelled": "task cancelled",
}


def _opaque_stage(stage: str) -> str:
    return stage if stage in _PUBLIC_STAGES else "processing"


async def _heartbeat_loop(
    progress_id: str,
    t0: float,
    stop_event: asyncio.Event,
    interval: float = 5.0,
) -> None:
    try:
        while True:
            try:
                await asyncio.wait_for(
                    stop_event.wait(), timeout=interval
                )
                break
            except asyncio.TimeoutError:
                pass
            elapsed = f"{time.monotonic() - t0:.1f}s"
            await append_lyrics_log(
                progress_id,
                f"[{elapsed}] \u23f3 still processing... (internal provider running)",
            )
    except asyncio.CancelledError:
        pass


async def _get_redis() -> Redis:  # type: ignore[type-arg]
    return Redis.from_url(
        settings.redis_url, decode_responses=True
    )


async def set_lyrics_progress(
    progress_id: str,
    stage: str,
    log_line: str | None = None,
) -> None:
    redis = await _get_redis()
    try:
        key = f"{PROGRESS_KEY_PREFIX}{progress_id}"
        data_raw = await redis.get(key)
        if data_raw:
            data = json.loads(data_raw)
        else:
            data = {"stage": stage, "logs": []}
        data["stage"] = stage
        if log_line:
            data["logs"] = data["logs"][-99:] + [
                log_line
            ]
        await redis.set(
            key, json.dumps(data), ex=_PROGRESS_TTL
        )
    finally:
        await redis.aclose()


async def append_lyrics_log(
    progress_id: str, log_line: str
) -> None:
    redis = await _get_redis()
    try:
        key = f"{PROGRESS_KEY_PREFIX}{progress_id}"
        data_raw = await redis.get(key)
        if data_raw:
            data = json.loads(data_raw)
        else:
            data = {"stage": "unknown", "logs": []}
        data["logs"] = data["logs"][-99:] + [
            log_line
        ]
        await redis.set(
            key, json.dumps(data), ex=_PROGRESS_TTL
        )
    finally:
        await redis.aclose()


async def get_lyrics_progress(
    progress_id: str,
) -> dict | None:
    redis = await _get_redis()
    try:
        raw = await redis.get(
            f"{PROGRESS_KEY_PREFIX}{progress_id}"
        )
        if not raw:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]
    finally:
        await redis.aclose()


async def _should_cancel(progress_id: str) -> bool:
    """Check if cancellation was requested for this task."""
    redis = await _get_redis()
    try:
        return await redis.exists(
            f"{CANCEL_KEY_PREFIX}{progress_id}"
        ) > 0
    finally:
        await redis.aclose()


async def _clear_cancel(progress_id: str) -> None:
    """Clear cancellation flag after handling."""
    redis = await _get_redis()
    try:
        await redis.delete(f"{CANCEL_KEY_PREFIX}{progress_id}")
    finally:
        await redis.aclose()


@broker.task
async def generate_lyrics_task(
    track_id: int,
    with_sync: bool = False,
    progress_id: str = "",
) -> dict:
    t0 = time.monotonic()
    structlog.contextvars.bind_contextvars(
        track_id=track_id, progress_id=progress_id
    )
    logger.info(
        "lyrics_generation_started",
        with_sync=with_sync,
    )

    def _elapsed() -> str:
        return f"{time.monotonic() - t0:.1f}s"

    async def _log(stage: str, msg: str) -> None:
        line = f"[{_elapsed()}] {msg}"
        logger.info(msg, stage=stage)
        await set_lyrics_progress(
            progress_id, stage, line
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Track).where(Track.id == track_id)
        )
        track = result.scalar_one_or_none()
        if not track or not track.is_active:
            await _log("error", "track not found")
            return {
                "status": "error",
                "detail": "track_not_found",
            }

        artist = track.artist or ""
        title = track.title or ""

        await _log(
            "searching",
            f"searching lyrics: artist={artist!r} title={title!r}",
        )

        audio_path: str | None = None
        tmp_dir: str | None = None

        try:
            # Check for cancellation before starting
            if await _should_cancel(progress_id):
                await _log(
                    "cancelled", "task cancelled by user"
                )
                await _clear_cancel(progress_id)
                return {"status": "cancelled"}

            if with_sync and (track.file_key or getattr(track, "sc_url", None)):
                await _log(
                    "downloading_audio",
                    "downloading audio for audio-based fallback",
                )
                tmp_dir = tempfile.mkdtemp()
                audio_path = await _fetch_audio_to_file(
                    track, tmp_dir, session
                )
                if audio_path:
                    size = os.path.getsize(audio_path)
                    await _log(
                        "downloading_audio",
                        f"audio ready: {size} bytes",
                    )
                else:
                    await _log(
                        "downloading_audio",
                        "audio unavailable, skipping audio-based fallback",
                    )

            from dotsound_private_core.services.lyrics_provider import (  # noqa: E501
                generate_lyrics,
            )

            loop = asyncio.get_running_loop()

            def on_progress(stage: str) -> None:
                opaque = _opaque_stage(stage)
                label = _STAGE_LABELS.get(opaque, "")
                desc = f" — {label}" if label else ""
                asyncio.run_coroutine_threadsafe(
                    _log(opaque, f"stage: {opaque}{desc}"),
                    loop,
                )

            await _log("searching", "calling lyrics provider")

            # Check for cancellation before starting generation
            if await _should_cancel(progress_id):
                await _log(
                    "cancelled",
                    "task cancelled by user before lyrics generation",
                )
                await _clear_cancel(progress_id)
                return {"status": "cancelled"}

            _stop_evt = asyncio.Event()
            _hb_task = asyncio.create_task(
                _heartbeat_loop(progress_id, t0, _stop_evt)
            )
            try:
                gen_result = await asyncio.to_thread(
                    generate_lyrics,
                    artist=artist,
                    title=title,
                    audio_path=audio_path,
                    on_progress=on_progress,
                )
            finally:
                _stop_evt.set()
                _hb_task.cancel()

            if gen_result is None:
                await _log(
                    "searching", "lyrics not found"
                )
                return {"status": "not_found"}

            await _log(
                "saving",
                f"lyrics found: {len(gen_result.text)} chars, "
                f"synced={gen_result.synced_lines is not None}",
            )

            synced_dicts: list[dict] | None = None
            if with_sync and gen_result.synced_lines:
                synced_dicts = [
                    {
                        "time_ms": sl.time_ms,
                        "text": sl.text,
                        "confidence": sl.confidence,
                    }
                    for sl in gen_result.synced_lines
                ]

            repo = LyricsRepository(session)
            await repo.create_or_update(
                track_id=track_id,
                plain_text=gen_result.text,
                source="auto",
                synced_lines=synced_dicts,
            )
            await session.commit()

            has_sync = synced_dicts is not None
            await _log(
                "saving",
                f"saved to DB (has_sync={has_sync})",
            )
            return {
                "status": "found",
                "has_sync": has_sync,
            }

        except Exception as exc:
            logger.exception("lyrics_generation_error")
            await _log(
                "error", f"ERROR: {exc}"
            )
            return {"status": "error"}
        finally:
            if tmp_dir and os.path.isdir(tmp_dir):
                import shutil

                shutil.rmtree(
                    tmp_dir, ignore_errors=True
                )


@broker.task
async def generate_lyrics_debug_task(
    track_id: int,
    stage_id: int,
    progress_id: str = "",
) -> dict:
    """Debug task: run only a specific provider stage in isolation."""
    t0 = time.monotonic()
    structlog.contextvars.bind_contextvars(
        track_id=track_id, progress_id=progress_id
    )
    logger.info(
        "lyrics_debug_started",
        stage_id=stage_id,
    )

    def _elapsed() -> str:
        return f"{time.monotonic() - t0:.1f}s"

    async def _log(stage: str, msg: str) -> None:
        line = f"[{_elapsed()}] {msg}"
        logger.info(msg, stage=stage)
        await set_lyrics_progress(
            progress_id, stage, line
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Track).where(Track.id == track_id)
        )
        track = result.scalar_one_or_none()
        if not track or not track.is_active:
            await _log("error", "track not found")
            return {
                "status": "error",
                "detail": "track_not_found",
            }

        artist = track.artist or ""
        title = track.title or ""

        await _log(
            "searching",
            f"[DEBUG] searching lyrics: artist={artist!r} title={title!r}",
        )

        # Check for cancellation before starting
        if await _should_cancel(progress_id):
            await _log(
                "cancelled", "task cancelled by user"
            )
            await _clear_cancel(progress_id)
            return {"status": "cancelled"}

        audio_path: str | None = None
        tmp_dir: str | None = None

        try:
            # Only download audio when the selected stage needs it.
            if stage_id == 3 and (
                track.file_key or getattr(track, "sc_url", None)
            ):
                await _log(
                    "downloading_audio",
                    "downloading audio for stage",
                )
                tmp_dir = tempfile.mkdtemp()
                audio_path = await _fetch_audio_to_file(
                    track, tmp_dir, session
                )
                if audio_path:
                    size = os.path.getsize(audio_path)
                    await _log(
                        "downloading_audio",
                        f"audio ready: {size} bytes",
                    )
                else:
                    await _log(
                        "downloading_audio",
                        "audio unavailable for stage",
                    )

            from dotsound_private_core.services.lyrics_provider import (
                generate_lyrics_debug,
            )

            loop = asyncio.get_running_loop()

            def on_progress(stage: str) -> None:
                opaque = _opaque_stage(stage)
                label = _STAGE_LABELS.get(opaque, "")
                desc = f" — {label}" if label else ""
                asyncio.run_coroutine_threadsafe(
                    _log(opaque, f"stage: {opaque}{desc}"),
                    loop,
                )

            import logging

            class _LogCapture(logging.Handler):
                def emit(self, record: logging.LogRecord) -> None:
                    msg = self.format(record)
                    asyncio.run_coroutine_threadsafe(
                        append_lyrics_log(progress_id, f"[{_elapsed()}] {msg}"),
                        loop,
                    )

            pc_logger = logging.getLogger(
                "dotsound_private_core.services.lyrics_provider"
            )
            handler = _LogCapture()
            handler.setLevel(logging.DEBUG)
            pc_logger.addHandler(handler)
            pc_logger.setLevel(logging.DEBUG)

            await _log("searching", "calling internal debug provider")

            # Check for cancellation before starting generation
            if await _should_cancel(progress_id):
                await _log(
                    "cancelled",
                    "task cancelled by user before lyrics generation",
                )
                await _clear_cancel(progress_id)
                return {"status": "cancelled"}

            _stop_evt = asyncio.Event()
            _hb_task = asyncio.create_task(
                _heartbeat_loop(progress_id, t0, _stop_evt)
            )
            try:
                gen_result = await asyncio.to_thread(
                    generate_lyrics_debug,
                    artist=artist,
                    title=title,
                    audio_path=audio_path,
                    tier=stage_id,
                    on_progress=on_progress,
                )
            finally:
                _stop_evt.set()
                _hb_task.cancel()
                pc_logger.removeHandler(handler)

            if gen_result is None:
                await _log(
                    "searching", "lyrics not found"
                )
                return {"status": "not_found"}

            await _log(
                "saving",
                f"lyrics found: {len(gen_result.text)} chars, "
                f"synced={gen_result.synced_lines is not None}",
            )

            # Debug mode: save plain text only (no synced lines)
            repo = LyricsRepository(session)
            await repo.create_or_update(
                track_id=track_id,
                plain_text=gen_result.text,
                source="auto",
                synced_lines=None,
            )
            await session.commit()

            await _log(
                "saving",
                f"saved to DB (debug mode, synced_lines ignored)",
            )
            return {
                "status": "found",
                "has_sync": False,
            }

        except Exception as exc:
            logger.exception("lyrics_generation_error")
            await _log(
                "error", f"ERROR: {exc}"
            )
            return {"status": "error"}
        finally:
            if tmp_dir and os.path.isdir(tmp_dir):
                import shutil

                shutil.rmtree(
                    tmp_dir, ignore_errors=True
                )
