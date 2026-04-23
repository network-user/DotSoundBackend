from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import unicodedata
import uuid

import structlog
from sqlalchemy import select
from taskiq import TaskiqEvents, TaskiqState

from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis_client
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


PROGRESS_KEY_PREFIX = "lyrics:progress:"
CANCEL_KEY_PREFIX = "lyrics:cancel:"
EVENTS_CHANNEL_PREFIX = "lyrics:events:"
SEARCH_CACHE_PREFIX = "lyrics:search:"
PARTIAL_KEY_PREFIX = "lyrics:partial:"
TRACK_LOCK_KEY_PREFIX = "lyrics:track_lock:"

_RELEASE_TRACK_LOCK_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


_PUBLIC_STAGES: frozenset[str] = frozenset(
    {
        "queued",
        "searching",
        "downloading_audio",
        "processing",
        "saving",
        "error",
        "cancelled",
        "cancelling",
    }
)

_STAGE_LABELS: dict[str, str] = {
    "queued": "waiting in queue",
    "searching": "looking up lyrics in sources",
    "downloading_audio": "downloading audio track",
    "processing": "audio-based provider processing (may take minutes)",
    "saving": "persisting results",
    "error": "error occurred",
    "cancelled": "task cancelled",
    "cancelling": "cancellation in progress",
}

TERMINAL_STATES: frozenset[str] = frozenset(
    {"found", "not_found", "error", "cancelled"}
)


def _opaque_stage(stage: str) -> str:
    return stage if stage in _PUBLIC_STAGES else "processing"


def _max_audio_bytes() -> int:
    return int(settings.lyrics_max_audio_mb) * 1024 * 1024


def _normalise_for_cache(value: str) -> str:
    normalised = unicodedata.normalize("NFKC", value or "")
    normalised = normalised.casefold().strip()
    normalised = re.sub(r"\s+", " ", normalised)
    return normalised


def _search_cache_key(artist: str, title: str) -> str:
    raw = f"{_normalise_for_cache(artist)}|" f"{_normalise_for_cache(title)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{SEARCH_CACHE_PREFIX}{digest[:32]}"


async def get_cached_lyrics_result(artist: str, title: str) -> dict | None:
    redis = get_redis_client()
    key = _search_cache_key(artist, title)
    raw = await redis.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        await redis.delete(key)
        return None


async def set_cached_lyrics_result(
    artist: str, title: str, payload: dict
) -> None:
    redis = get_redis_client()
    key = _search_cache_key(artist, title)
    await redis.set(
        key,
        json.dumps(payload, ensure_ascii=False),
        ex=int(settings.lyrics_search_cache_ttl_seconds),
    )


async def invalidate_cached_lyrics_result(artist: str, title: str) -> None:
    redis = get_redis_client()
    await redis.delete(_search_cache_key(artist, title))


def _cache_keys_for_track(artist: str, title: str) -> list[str]:
    """Cache keys covering every search attempt for this track.

    Mirrors :func:`_lyrics_search_attempts` so callers can wipe the
    artist+title key together with its title-only fallback in one
    Redis ``DEL``.
    """
    seen: set[str] = set()
    keys: list[str] = []
    for cache_artist, cache_title, _mode in _lyrics_search_attempts(
        artist, title
    ):
        key = _search_cache_key(cache_artist, cache_title)
        if key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


async def invalidate_cached_lyrics_for_track(artist: str, title: str) -> None:
    """Wipe every cache key associated with ``(artist, title)``.

    Unlike :func:`invalidate_cached_lyrics_result`, this also drops
    the title-only fallback entry so a follow-up redefine cannot be
    silently served from a stale alias.
    """
    keys = _cache_keys_for_track(artist, title)
    if not keys:
        return
    redis = get_redis_client()
    await redis.delete(*keys)


def _cached_satisfies_request(cached: dict | None, with_sync: bool) -> bool:
    """Whether a cached payload covers the current request.

    Text-only requests are happy with anything that has ``text``.
    Sync requests additionally require non-empty ``synced_lines`` so
    we never hand back a text-only cache as if it were aligned.
    """
    if not isinstance(cached, dict):
        return False
    if not cached.get("text"):
        return False
    if with_sync:
        synced = cached.get("synced_lines")
        if not isinstance(synced, list) or not synced:
            return False
    return True


def _events_channel(progress_id: str) -> str:
    return f"{EVENTS_CHANNEL_PREFIX}{progress_id}"


async def _publish_event(progress_id: str, payload: dict) -> None:
    redis = get_redis_client()
    try:
        await redis.publish(
            _events_channel(progress_id),
            json.dumps(payload, ensure_ascii=False),
        )
    except Exception:
        logger.debug(
            "lyrics_event_publish_failed",
            progress_id=progress_id,
        )


async def store_partial_text(progress_id: str, plain_text: str) -> None:
    if not plain_text:
        return
    redis = get_redis_client()
    payload = {"plain_text": plain_text}
    await redis.set(
        f"{PARTIAL_KEY_PREFIX}{progress_id}",
        json.dumps(payload, ensure_ascii=False),
        ex=int(settings.lyrics_partial_ttl_seconds),
    )
    await _publish_event(
        progress_id,
        {"type": "partial.text", "plain_text": plain_text},
    )


async def store_partial_synced(
    progress_id: str, synced_lines: list[dict]
) -> None:
    if not synced_lines:
        return
    redis = get_redis_client()
    key = f"{PARTIAL_KEY_PREFIX}{progress_id}"
    raw = await redis.get(key)
    data: dict = {}
    if raw:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = {}
    data["synced_lines"] = synced_lines
    await redis.set(
        key,
        json.dumps(data, ensure_ascii=False),
        ex=int(settings.lyrics_partial_ttl_seconds),
    )
    await _publish_event(
        progress_id,
        {"type": "partial.synced", "synced_lines": synced_lines},
    )


async def get_partial_result(
    progress_id: str,
) -> dict | None:
    redis = get_redis_client()
    raw = await redis.get(f"{PARTIAL_KEY_PREFIX}{progress_id}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


async def set_lyrics_progress(
    progress_id: str,
    stage: str | None = None,
    log_line: str | None = None,
    *,
    terminal_state: str | None = None,
    percent: int | None = None,
    meta: dict | None = None,
) -> None:
    """Update lyrics progress snapshot in Redis.

    Keeps only the most recent 100 log lines. Publishes a
    matching event to Pub/Sub so SSE subscribers stay in sync
    without polling.
    """
    redis = get_redis_client()
    key = f"{PROGRESS_KEY_PREFIX}{progress_id}"
    raw = await redis.get(key)
    if raw:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = {}
    else:
        data = {}
    data.setdefault("logs", [])
    data.setdefault("stage", stage or "queued")

    if stage is not None:
        data["stage"] = stage
    if terminal_state is not None:
        data["terminal_state"] = terminal_state
    if percent is not None:
        data["percent"] = max(0, min(100, int(percent)))
    if log_line:
        data["logs"] = (data.get("logs") or [])[-99:] + [log_line]

    await redis.set(
        key,
        json.dumps(data, ensure_ascii=False),
        ex=int(settings.lyrics_progress_ttl_seconds),
    )

    event: dict = {"type": "progress"}
    if stage is not None:
        event["stage"] = data.get("stage")
    if terminal_state is not None:
        event["terminal_state"] = terminal_state
    if "percent" in data:
        event["percent"] = data["percent"]
    if log_line:
        event["log"] = log_line
    if meta:
        event["meta"] = meta
    await _publish_event(progress_id, event)


async def append_lyrics_log(progress_id: str, log_line: str) -> None:
    await set_lyrics_progress(progress_id, log_line=log_line)


async def get_lyrics_progress(
    progress_id: str,
) -> dict | None:
    redis = get_redis_client()
    raw = await redis.get(f"{PROGRESS_KEY_PREFIX}{progress_id}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


async def _should_cancel(progress_id: str) -> bool:
    redis = get_redis_client()
    return (await redis.exists(f"{CANCEL_KEY_PREFIX}{progress_id}")) > 0


async def _clear_cancel(progress_id: str) -> None:
    redis = get_redis_client()
    await redis.delete(f"{CANCEL_KEY_PREFIX}{progress_id}")


async def _try_acquire_track_lock(
    track_id: int, owner_token: str, ttl_seconds: int
) -> bool:
    """Atomic SET NX EX. Returns True when this caller now owns the
    per-track lock for ``track_id``; False when another worker holds
    it. Auto-expires after ``ttl_seconds`` so a crashed worker
    doesn't permanently block re-runs.
    """
    redis = get_redis_client()
    key = f"{TRACK_LOCK_KEY_PREFIX}{track_id}"
    result = await redis.set(
        key,
        owner_token,
        nx=True,
        ex=int(ttl_seconds),
    )
    return bool(result)


async def _release_track_lock(track_id: int, owner_token: str) -> None:
    """Release the per-track lock only if this caller still owns
    it. If the TTL already expired and another caller picked it up,
    we leave their lock alone.
    """
    try:
        redis = get_redis_client()
        key = f"{TRACK_LOCK_KEY_PREFIX}{track_id}"
        await redis.eval(_RELEASE_TRACK_LOCK_LUA, 1, key, owner_token)
    except Exception:
        logger.debug("lyrics_track_lock_release_failed", track_id=track_id)


async def _finalise(
    progress_id: str, terminal_state: str, log_line: str | None = None
) -> None:
    stage = terminal_state
    if terminal_state == "found":
        stage = "saving"
    elif terminal_state == "not_found":
        stage = "searching"
    percent = 100 if terminal_state == "found" else None
    await set_lyrics_progress(
        progress_id,
        stage=stage,
        terminal_state=terminal_state,
        percent=percent,
        log_line=log_line,
    )


async def _stream_http_to_file(
    client,  # httpx.AsyncClient
    url: str,
    path: str,
    max_bytes: int,
) -> int:
    """Stream an HTTP response body to disk with size cap.

    Raises ValueError if the response exceeds ``max_bytes``.
    """
    async with client.stream("GET", url) as resp:
        resp.raise_for_status()
        written = 0
        with open(path, "wb") as f:
            async for chunk in resp.aiter_bytes(chunk_size=65536):
                if not chunk:
                    continue
                written += len(chunk)
                if written > max_bytes:
                    raise ValueError(
                        f"audio exceeds lyrics_max_audio_mb limit "
                        f"({settings.lyrics_max_audio_mb} MB)"
                    )
                f.write(chunk)
        return written


async def _hls_to_file(m3u8_url: str, path: str) -> bool:
    """Download an HLS playlist into a local mp4 using ffmpeg.

    Returns True on success, False when ffmpeg is unavailable or
    fails. The output is stream-copied, so no re-encoding happens.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.info("lyrics_ffmpeg_unavailable")
        return False
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-protocol_whitelist",
        "file,http,https,tcp,tls,crypto",
        "-i",
        m3u8_url,
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        "-y",
        path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.warning(
            "lyrics_ffmpeg_failed",
            rc=proc.returncode,
            stderr=(stderr or b"")[-512:].decode("utf-8", errors="replace"),
        )
        return False
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    if size <= 0:
        return False
    max_bytes = _max_audio_bytes()
    if size > max_bytes:
        os.remove(path)
        logger.warning(
            "lyrics_ffmpeg_oversize",
            size=size,
            max_bytes=max_bytes,
        )
        return False
    return True


async def _fetch_audio_to_file(
    track: Track,
    tmp_dir: str,
    session,  # AsyncSession
) -> str | None:
    """Download track audio to a temp file, streaming with a cap.

    Handles both internal (S3) and SoundCloud tracks. For HLS
    SoundCloud streams ffmpeg is used to remux into a local mp4,
    when available. Returns local file path, or None if audio is
    unavailable or exceeds configured limits.
    """
    max_bytes = _max_audio_bytes()

    if track.file_key:
        data = await s3.download_object(track.file_key)
        if len(data) > max_bytes:
            logger.warning(
                "lyrics_s3_audio_oversize",
                size=len(data),
                max_bytes=max_bytes,
                track_id=track.id,
            )
            return None
        path = os.path.join(tmp_dir, "audio.mp3")
        with open(path, "wb") as f:
            f.write(data)
        return path

    if getattr(track, "sc_url", None):
        try:
            import httpx
            from app.services.soundcloud_service import (
                SoundCloudService,
            )

            sc = SoundCloudService(settings.sc_client_id, session)
            stream_url, protocol = await sc.get_stream_info(track.sc_url)

            if protocol == "progressive":
                path = os.path.join(tmp_dir, "audio.mp3")
                async with httpx.AsyncClient(
                    timeout=120, follow_redirects=True
                ) as client:
                    try:
                        await _stream_http_to_file(
                            client, stream_url, path, max_bytes
                        )
                    except ValueError:
                        logger.warning(
                            "lyrics_sc_audio_oversize",
                            track_id=track.id,
                        )
                        return None
                return path

            path = os.path.join(tmp_dir, "audio.mp4")
            ok = await _hls_to_file(stream_url, path)
            if not ok:
                logger.info(
                    "lyrics_sc_hls_fallback_failed",
                    track_id=track.id,
                )
                return None
            return path
        except Exception:
            logger.exception("sc_audio_download_failed", track_id=track.id)
            return None

    return None


_HEARTBEAT_MSGS: tuple[str, ...] = (
    "audio analysis running",
    "still processing \u2014 audio-based alignment can take a few minutes",
    "still running, provider is busy",
    "audio analysis in progress, almost there",
    "still going \u2014 longer tracks take more time",
)


async def _heartbeat_loop(
    progress_id: str,
    t0: float,
    stop_event: asyncio.Event,
    interval: float = 5.0,
    eta_ms: int | None = None,
) -> None:
    tick = 0
    try:
        while True:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                pass
            elapsed_s = time.monotonic() - t0
            elapsed = f"{elapsed_s:.0f}s"
            msg = _HEARTBEAT_MSGS[tick % len(_HEARTBEAT_MSGS)]
            tick += 1

            eta_suffix = ""
            if eta_ms is not None:
                remaining_s = eta_ms / 1000 - elapsed_s
                if remaining_s > 10:
                    eta_suffix = f" (~{remaining_s:.0f}s remaining)"
            await append_lyrics_log(
                progress_id,
                f"[{elapsed}] \u23f3 {msg}{eta_suffix}",
            )
    except asyncio.CancelledError:
        pass


def _parse_progress_event(event) -> tuple[str, int | None]:
    """Accept both legacy ``str`` and future structured dict progress.

    Returns ``(stage, percent)`` — percent is None if not supplied.
    """
    if isinstance(event, str):
        return event, None
    if isinstance(event, dict):
        stage = str(event.get("stage") or "processing")
        raw_percent = event.get("percent")
        percent: int | None = None
        if isinstance(raw_percent, (int, float)):
            percent = max(0, min(100, int(raw_percent)))
        return stage, percent
    return "processing", None


def _call_provider(
    func,
    *,
    artist: str,
    title: str,
    audio_path: str | None,
    on_progress,
    on_cancel,
    tier: int | None = None,
    external_id: str | None = None,
) -> object:
    """Invoke a lyrics provider entry point with graceful kw fallback.

    Older provider versions may not accept ``on_cancel`` or
    ``external_id``; we try the richest call first and degrade
    gracefully.
    """
    kwargs = {
        "artist": artist,
        "title": title,
        "audio_path": audio_path,
        "on_progress": on_progress,
    }
    if tier is not None:
        kwargs["tier"] = tier
    extra = {"on_cancel": on_cancel}
    if external_id is not None:
        extra["external_id"] = external_id
    try:
        return func(**kwargs, **extra)
    except TypeError:
        pass
    # Drop external_id and retry (older provider without that kwarg).
    try:
        return func(**kwargs, on_cancel=on_cancel)
    except TypeError:
        return func(**kwargs)


_ALLOWED_SYNC_QUALITY = {"line", "word", "none"}
_ALLOWED_SYNC_PROFILE = {"cpu_light", "gpu_full"}


def _word_times_from(sl) -> list[dict] | None:
    raw = getattr(sl, "word_times", None)
    if not raw:
        return None
    parsed: list[dict] = []
    for wt in raw:
        try:
            text = str(getattr(wt, "text", "") or "")
            start_ms = int(getattr(wt, "start_ms", 0) or 0)
            dur_ms = int(getattr(wt, "dur_ms", 0) or 0)
            conf = getattr(wt, "confidence", 0.0)
            conf = float(conf) if conf is not None else 0.0
        except (TypeError, ValueError):
            continue
        if start_ms < 0 or dur_ms < 0:
            continue
        parsed.append(
            {
                "text": text[:200],
                "start_ms": start_ms,
                "dur_ms": dur_ms,
                "confidence": max(0.0, min(1.0, conf)),
            }
        )
    return parsed or None


def _payload_has_non_empty_synced(payload: dict) -> bool:
    """True when ``synced_lines`` is a non-empty list of line dicts."""
    sl = payload.get("synced_lines")
    return isinstance(sl, list) and len(sl) > 0


def _result_to_payload(gen_result) -> dict:
    synced: list[dict] | None = None
    if gen_result.synced_lines:
        synced = []
        for sl in gen_result.synced_lines:
            line: dict = {
                "time_ms": int(sl.time_ms),
                "text": sl.text,
                "confidence": (
                    float(sl.confidence) if sl.confidence is not None else 0.0
                ),
            }
            wts = _word_times_from(sl)
            if wts is not None:
                line["word_times"] = wts
            synced.append(line)

    sync_quality = getattr(gen_result, "sync_quality", None)
    if sync_quality not in _ALLOWED_SYNC_QUALITY:
        sync_quality = None
    sync_profile = getattr(gen_result, "sync_profile", None)
    if sync_profile not in _ALLOWED_SYNC_PROFILE:
        sync_profile = None

    source_name = getattr(gen_result, "source_name", None)
    if not isinstance(source_name, str) or not source_name.strip():
        source_name = None

    sync_source_name = getattr(gen_result, "sync_source_name", None)
    if not isinstance(sync_source_name, str) or not sync_source_name.strip():
        sync_source_name = None

    return {
        "text": gen_result.text,
        "synced_lines": synced,
        "sync_quality": sync_quality,
        "sync_profile": sync_profile,
        "source_name": source_name,
        "sync_source_name": sync_source_name,
    }


def _lyrics_search_attempts(
    artist: str, title: str
) -> list[tuple[str, str, str]]:
    attempts: list[tuple[str, str, str]] = [(artist, title, "artist_title")]
    if artist.strip():
        attempts.append(("", title, "title_only"))
    return attempts


@broker.task
async def generate_lyrics_task(
    track_id: int,
    with_sync: bool = False,
    progress_id: str = "",
    bypass_cache: bool = False,
) -> dict:
    """Outer Taskiq entry point.

    Owns the per-track Redis lock so two concurrent imports for
    the same track_id collapse to a single provider call. The real
    work lives in :func:`_generate_lyrics_task_impl` so we can
    wrap it in try/finally without indenting the whole body.
    """
    lock_owner_token = progress_id or uuid.uuid4().hex
    lock_acquired = await _try_acquire_track_lock(
        track_id,
        lock_owner_token,
        settings.lyrics_per_track_lock_ttl_seconds,
    )
    if not lock_acquired:
        logger.info(
            "lyrics_task_skipped_lock_held",
            track_id=track_id,
        )
        return {
            "status": "skipped",
            "reason": "already_running",
        }
    try:
        return await _generate_lyrics_task_impl(
            track_id=track_id,
            with_sync=with_sync,
            progress_id=progress_id,
            bypass_cache=bypass_cache,
        )
    finally:
        await _release_track_lock(track_id, lock_owner_token)


async def _generate_lyrics_task_impl(
    *,
    track_id: int,
    with_sync: bool,
    progress_id: str,
    bypass_cache: bool,
) -> dict:
    from app.services.lyrics_eta import (
        publish_initial_eta,
        record_stage_duration,
    )

    t0 = time.monotonic()
    stage_started: dict[str, float] = {}
    last_stage: str | None = None
    profile = "cpu_light"

    structlog.contextvars.bind_contextvars(
        track_id=track_id, progress_id=progress_id
    )
    logger.info(
        "lyrics_generation_started",
        with_sync=with_sync,
        bypass_cache=bypass_cache,
    )

    try:
        _eta_ms: int | None = await publish_initial_eta(progress_id, profile)
    except Exception:
        _eta_ms = None

    def _elapsed() -> str:
        return f"{time.monotonic() - t0:.1f}s"

    async def _log(
        stage: str,
        msg: str,
        *,
        percent: int | None = None,
    ) -> None:
        nonlocal last_stage
        line = f"[{_elapsed()}] {msg}"
        logger.info(msg, stage=stage)
        if stage != last_stage:
            now = time.monotonic()
            if last_stage and last_stage in stage_started:
                duration_ms = int((now - stage_started[last_stage]) * 1000)
                try:
                    await record_stage_duration(
                        profile, last_stage, duration_ms
                    )
                except Exception:
                    pass
            stage_started[stage] = now
            last_stage = stage
        await set_lyrics_progress(
            progress_id,
            stage=stage,
            log_line=line,
            percent=percent,
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Track).where(Track.id == track_id)
        )
        track = result.scalar_one_or_none()
        if not track or not track.is_active:
            await _finalise(
                progress_id,
                "error",
                log_line=f"[{_elapsed()}] ERROR: track not found",
            )
            return {
                "status": "error",
                "detail": "track_not_found",
            }

        artist = track.artist or ""
        title = track.title or ""
        search_attempts = _lyrics_search_attempts(artist, title)

        await _log(
            "searching",
            f"searching lyrics: artist={artist!r} title={title!r}",
            percent=5,
        )

        if bypass_cache:
            await _log(
                "searching",
                "cache bypass enabled for this run",
                percent=8,
            )
        else:
            for (
                cache_artist,
                cache_title,
                cache_mode,
            ) in search_attempts:
                cached = await get_cached_lyrics_result(
                    cache_artist, cache_title
                )
                if not _cached_satisfies_request(cached, with_sync):
                    if (
                        with_sync
                        and isinstance(cached, dict)
                        and cached.get("text")
                    ):
                        # Pre-save the cached text so the user sees
                        # lyrics immediately while sync runs. Break
                        # out of the cache loop to proceed with the
                        # audio-based sync upgrade.
                        try:
                            repo_early = LyricsRepository(session)
                            await repo_early.create_or_update(
                                track_id=track_id,
                                plain_text=cached["text"],
                                source="auto",
                                synced_lines=None,
                                sync_quality=None,
                                sync_profile=None,
                            )
                            await session.commit()
                        except Exception:
                            logger.debug(
                                "lyrics_early_text_save_failed",
                                track_id=track_id,
                            )
                        await _log(
                            "searching",
                            "cache text pre-saved; running sync "
                            "stage from audio",
                            percent=12,
                        )
                        break
                    continue

                cached_synced_raw = cached.get("synced_lines")
                cached_synced: list[dict] | None = None
                if (
                    with_sync
                    and isinstance(cached_synced_raw, list)
                    and cached_synced_raw
                ):
                    cached_synced = list(cached_synced_raw)

                if cache_mode == "artist_title":
                    cache_log = "cache hit: reusing previous lyrics " "result"
                else:
                    cache_log = (
                        "cache hit: reusing title-only " "fallback result"
                    )
                if cached_synced is not None:
                    cache_log += " (with timecodes)"
                await _log(
                    "saving",
                    cache_log,
                    percent=90,
                )
                repo = LyricsRepository(session)
                await repo.create_or_update(
                    track_id=track_id,
                    plain_text=cached["text"],
                    source="auto",
                    synced_lines=cached_synced,
                    sync_quality=cached.get("sync_quality"),
                    sync_profile=cached.get("sync_profile"),
                    source_name=cached.get("source_name"),
                    sync_source_name=cached.get("sync_source_name"),
                )
                await session.commit()

                if cached_synced is not None:
                    try:
                        await store_partial_synced(progress_id, cached_synced)
                    except Exception:
                        pass

                if cache_mode != "artist_title":
                    try:
                        await set_cached_lyrics_result(artist, title, cached)
                    except Exception:
                        logger.debug(
                            "lyrics_cache_alias_write_failed",
                            track_id=track_id,
                        )

                await _finalise(
                    progress_id,
                    "found",
                    log_line=(
                        f"[{_elapsed()}] saved to DB (cache, "
                        f"has_sync={cached_synced is not None})"
                    ),
                )
                return {
                    "status": "found",
                    "has_sync": cached_synced is not None,
                    "cache": True,
                }

        audio_path: str | None = None
        tmp_dir: str | None = None

        try:
            if await _should_cancel(progress_id):
                await _finalise(
                    progress_id,
                    "cancelled",
                    log_line=(f"[{_elapsed()}] task cancelled by user"),
                )
                await _clear_cancel(progress_id)
                return {"status": "cancelled"}

            if with_sync and (
                track.file_key or getattr(track, "sc_url", None)
            ):
                await _log(
                    "downloading_audio",
                    "downloading audio for audio-based fallback",
                    percent=15,
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
                        percent=25,
                    )
                else:
                    await _log(
                        "downloading_audio",
                        "audio unavailable, skipping audio-based " "fallback",
                        percent=25,
                    )

            from dotsound_private_core.services.lyrics_provider import (  # noqa: E501
                generate_lyrics,
            )

            loop = asyncio.get_running_loop()

            def on_progress(event) -> None:
                stage, percent_val = _parse_progress_event(event)
                opaque = _opaque_stage(stage)
                label = _STAGE_LABELS.get(opaque, "")
                desc = f" \u2014 {label}" if label else ""
                asyncio.run_coroutine_threadsafe(
                    _log(
                        opaque,
                        f"stage: {opaque}{desc}",
                        percent=percent_val,
                    ),
                    loop,
                )

            def on_cancel() -> bool:
                fut = asyncio.run_coroutine_threadsafe(
                    _should_cancel(progress_id), loop
                )
                try:
                    return bool(fut.result(timeout=2))
                except Exception:
                    return False

            gen_result = None
            used_artist = artist
            used_title = title
            used_mode = "artist_title"

            for attempt_idx, (
                attempt_artist,
                attempt_title,
                attempt_mode,
            ) in enumerate(search_attempts):
                if await _should_cancel(progress_id):
                    await _finalise(
                        progress_id,
                        "cancelled",
                        log_line=(
                            f"[{_elapsed()}] task cancelled by user "
                            "before lyrics generation"
                        ),
                    )
                    await _clear_cancel(progress_id)
                    return {"status": "cancelled"}

                if attempt_idx > 0:
                    await _log(
                        "searching",
                        "retrying lyrics search with title-only " "fallback",
                        percent=38,
                    )

                attempt_label = (
                    "title-only fallback"
                    if attempt_mode == "title_only"
                    else "artist+title"
                )
                await _log(
                    "searching",
                    f"calling lyrics provider ({attempt_label})",
                    percent=30 if attempt_idx == 0 else 40,
                )

                _stop_evt = asyncio.Event()
                _hb_task = asyncio.create_task(
                    _heartbeat_loop(progress_id, t0, _stop_evt, eta_ms=_eta_ms)
                )
                try:
                    current_result = await asyncio.wait_for(
                        asyncio.to_thread(
                            _call_provider,
                            generate_lyrics,
                            artist=attempt_artist,
                            title=attempt_title,
                            audio_path=audio_path,
                            on_progress=on_progress,
                            on_cancel=on_cancel,
                            external_id=track.external_id,
                        ),
                        timeout=float(
                            settings.lyrics_provider_timeout_seconds
                        ),
                    )
                except asyncio.TimeoutError:
                    _stop_evt.set()
                    _hb_task.cancel()
                    redis = get_redis_client()
                    await redis.set(
                        f"{CANCEL_KEY_PREFIX}{progress_id}",
                        "1",
                        ex=120,
                    )
                    await _finalise(
                        progress_id,
                        "error",
                        log_line=(
                            f"[{_elapsed()}] ERROR: provider timed out "
                            f"after {settings.lyrics_provider_timeout_seconds}s"
                        ),
                    )
                    return {"status": "error", "detail": "timeout"}
                finally:
                    _stop_evt.set()
                    _hb_task.cancel()

                if current_result is not None:
                    gen_result = current_result
                    used_artist = attempt_artist
                    used_title = attempt_title
                    used_mode = attempt_mode
                    break

            if gen_result is None:
                await _finalise(
                    progress_id,
                    "not_found",
                    log_line=(f"[{_elapsed()}] lyrics not found"),
                )
                return {"status": "not_found"}

            await _log(
                "saving",
                f"lyrics found: {len(gen_result.text)} chars, "
                f"synced={gen_result.synced_lines is not None}",
                percent=85,
            )
            if used_mode == "title_only":
                await _log(
                    "saving",
                    "lyrics resolved via title-only fallback",
                    percent=82,
                )

            payload = _result_to_payload(gen_result)
            cache_pairs = {
                (artist, title),
                (used_artist, used_title),
            }
            for cache_artist, cache_title in cache_pairs:
                try:
                    await set_cached_lyrics_result(
                        cache_artist, cache_title, payload
                    )
                except Exception:
                    logger.debug(
                        "lyrics_cache_write_failed",
                        track_id=track_id,
                    )

            try:
                await store_partial_text(progress_id, payload["text"])
            except Exception:
                pass

            synced_dicts: list[dict] | None = None
            if with_sync and payload["synced_lines"]:
                synced_dicts = payload["synced_lines"]
                try:
                    await store_partial_synced(progress_id, synced_dicts)
                except Exception:
                    pass
            elif with_sync:
                await _log(
                    "saving",
                    "alignment did not produce timecodes "
                    "\u2014 saving text only",
                    percent=86,
                )

            repo = LyricsRepository(session)
            await repo.create_or_update(
                track_id=track_id,
                plain_text=payload["text"],
                source="auto",
                synced_lines=synced_dicts,
                sync_quality=payload.get("sync_quality"),
                sync_profile=payload.get("sync_profile"),
                source_name=payload.get("source_name"),
                sync_source_name=payload.get("sync_source_name"),
            )
            await session.commit()

            has_sync = synced_dicts is not None
            await _finalise(
                progress_id,
                "found",
                log_line=(
                    f"[{_elapsed()}] saved to DB " f"(has_sync={has_sync})"
                ),
            )
            return {
                "status": "found",
                "has_sync": has_sync,
            }

        except Exception as exc:
            logger.exception("lyrics_generation_error")
            await _finalise(
                progress_id,
                "error",
                log_line=f"[{_elapsed()}] ERROR: {exc}",
            )
            return {"status": "error"}
        finally:
            if tmp_dir and os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)


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

    async def _log(
        stage: str,
        msg: str,
        *,
        percent: int | None = None,
    ) -> None:
        line = f"[{_elapsed()}] {msg}"
        logger.info(msg, stage=stage)
        await set_lyrics_progress(
            progress_id,
            stage=stage,
            log_line=line,
            percent=percent,
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Track).where(Track.id == track_id)
        )
        track = result.scalar_one_or_none()
        if not track or not track.is_active:
            await _finalise(
                progress_id,
                "error",
                log_line=f"[{_elapsed()}] ERROR: track not found",
            )
            return {
                "status": "error",
                "detail": "track_not_found",
            }

        artist = track.artist or ""
        title = track.title or ""

        await _log(
            "searching",
            f"[DEBUG] searching lyrics: artist={artist!r} " f"title={title!r}",
            percent=5,
        )

        if await _should_cancel(progress_id):
            await _finalise(
                progress_id,
                "cancelled",
                log_line=(f"[{_elapsed()}] task cancelled by user"),
            )
            await _clear_cancel(progress_id)
            return {"status": "cancelled"}

        audio_path: str | None = None
        tmp_dir: str | None = None

        try:
            if stage_id == 3 and (
                track.file_key or getattr(track, "sc_url", None)
            ):
                await _log(
                    "downloading_audio",
                    "downloading audio for stage",
                    percent=20,
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
                        percent=30,
                    )
                else:
                    await _log(
                        "downloading_audio",
                        "audio unavailable for stage",
                        percent=30,
                    )

            from dotsound_private_core.services.lyrics_provider import (  # noqa: E501
                generate_lyrics_debug,
            )

            loop = asyncio.get_running_loop()

            def on_progress(event) -> None:
                stage, percent_val = _parse_progress_event(event)
                opaque = _opaque_stage(stage)
                label = _STAGE_LABELS.get(opaque, "")
                desc = f" \u2014 {label}" if label else ""
                asyncio.run_coroutine_threadsafe(
                    _log(
                        opaque,
                        f"stage: {opaque}{desc}",
                        percent=percent_val,
                    ),
                    loop,
                )

            def on_cancel() -> bool:
                fut = asyncio.run_coroutine_threadsafe(
                    _should_cancel(progress_id), loop
                )
                try:
                    return bool(fut.result(timeout=2))
                except Exception:
                    return False

            import logging

            class _LogCapture(logging.Handler):
                def emit(self, record: logging.LogRecord) -> None:
                    msg = self.format(record)
                    asyncio.run_coroutine_threadsafe(
                        append_lyrics_log(
                            progress_id,
                            f"[{_elapsed()}] {msg}",
                        ),
                        loop,
                    )

            pc_logger = logging.getLogger(
                "dotsound_private_core.services.lyrics_provider"
            )
            handler = _LogCapture()
            handler.setLevel(logging.DEBUG)
            pc_logger.addHandler(handler)
            pc_logger.setLevel(logging.DEBUG)

            await _log(
                "searching",
                "calling internal debug provider",
                percent=40,
            )

            if await _should_cancel(progress_id):
                await _finalise(
                    progress_id,
                    "cancelled",
                    log_line=(
                        f"[{_elapsed()}] task cancelled by user "
                        "before lyrics generation"
                    ),
                )
                await _clear_cancel(progress_id)
                return {"status": "cancelled"}

            _stop_evt = asyncio.Event()
            _hb_task = asyncio.create_task(
                _heartbeat_loop(progress_id, t0, _stop_evt)
            )
            try:
                gen_result = await asyncio.to_thread(
                    _call_provider,
                    generate_lyrics_debug,
                    artist=artist,
                    title=title,
                    audio_path=audio_path,
                    on_progress=on_progress,
                    on_cancel=on_cancel,
                    tier=stage_id,
                )
            finally:
                _stop_evt.set()
                _hb_task.cancel()
                pc_logger.removeHandler(handler)

            if gen_result is None:
                await _finalise(
                    progress_id,
                    "not_found",
                    log_line=(f"[{_elapsed()}] lyrics not found"),
                )
                return {"status": "not_found"}

            await _log(
                "saving",
                f"lyrics found: {len(gen_result.text)} chars, "
                f"synced={gen_result.synced_lines is not None}",
                percent=85,
            )

            repo = LyricsRepository(session)
            await repo.create_or_update(
                track_id=track_id,
                plain_text=gen_result.text,
                source="auto",
                synced_lines=None,
            )
            await session.commit()

            await _finalise(
                progress_id,
                "found",
                log_line=(
                    f"[{_elapsed()}] saved to DB "
                    "(debug mode, synced_lines ignored)"
                ),
            )
            return {
                "status": "found",
                "has_sync": False,
            }

        except Exception as exc:
            logger.exception("lyrics_generation_error")
            await _finalise(
                progress_id,
                "error",
                log_line=f"[{_elapsed()}] ERROR: {exc}",
            )
            return {"status": "error"}
        finally:
            if tmp_dir and os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)


def _close_job_attempt(job, *, status: str, error: str | None = None) -> None:
    """Mutate the last entry in ``job.tier_attempts`` in place.

    Mirrors the equivalent helper in ``lyrics_cascade.py`` to
    avoid a circular import; both must agree on the entry shape.
    """
    raw = list(job.tier_attempts or [])
    if not raw:
        return
    last = dict(raw[-1])
    if last.get("status") in {"queued", "running"}:
        from datetime import datetime, timezone

        last["finished_at"] = datetime.now(timezone.utc).isoformat()
        last["status"] = status
        if error is not None:
            last["error"] = (error or "")[:512]
        raw[-1] = last
        job.tier_attempts = raw


async def _save_catalog_result_and_close(
    session,
    *,
    job,
    payload: dict,
    progress_id: str,
    with_sync: bool,
) -> None:
    from datetime import datetime, timezone

    from app.core.observability import lyrics_job_observed

    synced_dicts: list[dict] | None = None
    if with_sync and payload.get("synced_lines"):
        synced_dicts = payload["synced_lines"]
    repo = LyricsRepository(session)
    await repo.create_or_update(
        track_id=job.track_id,
        plain_text=payload["text"],
        source="auto",
        synced_lines=synced_dicts,
        sync_quality=payload.get("sync_quality"),
        sync_profile=payload.get("sync_profile"),
        source_name=payload.get("source_name"),
    )
    _close_job_attempt(job, status="success")
    job.status = "done"
    job.finished_at = datetime.now(timezone.utc)
    started = job.started_at or job.created_at
    duration_seconds = 0.0
    if started:
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        duration_seconds = (
            datetime.now(timezone.utc) - started
        ).total_seconds()
        job.duration_ms = int(duration_seconds * 1000)
    try:
        lyrics_job_observed(
            tier=job.current_tier or "catalog_only",
            status="success",
            duration_seconds=duration_seconds,
        )
    except Exception:
        pass


@broker.task
async def catalog_only_lyrics_task(
    track_id: int,
    with_sync: bool = False,
    progress_id: str = "",
    bypass_cache: bool = False,
    job_id: str = "",
) -> dict:
    """Tier 1: catalog-only lyrics fetch (no local ASR).

    Calls PrivateCore's ``generate_lyrics`` with
    ``disable_local_asr=True`` so faster-whisper is never imported
    on the Backend. On a full hit the lyrics + LyricsJob are
    saved and the job goes to ``status="done"``. If
    ``with_sync=True`` but the catalog only returned plain text
    (no ``synced_lines``), the job is *not* closed: we
    :func:`handle_tier_miss` so the cascade can hand audio work to
    the next tier (e.g. remote ASR) for time-aligned output. A pure
    miss (``gen_result is None``) is handled the same way. On a miss
    the cascade is asked for the next tier
    (``lyrics_cascade.handle_tier_miss``).

    The dev escape hatch ``LYRICS_ALLOW_LOCAL_ASR=true`` is
    honoured only when ``DEBUG=true`` (config validator enforces
    this) — when both flags are on the task downloads audio and
    runs ASR in-process for fast local iteration.
    """
    from dotsound_private_core.services.lyrics_provider import (
        generate_lyrics,
    )

    structlog.contextvars.bind_contextvars(
        track_id=track_id,
        progress_id=progress_id,
        correlation_id=job_id or progress_id,
        tier="catalog_only",
    )
    logger.info(
        "catalog_only_started",
        with_sync=with_sync,
        bypass_cache=bypass_cache,
        job_id=job_id,
    )

    use_local_asr = bool(settings.debug and settings.lyrics_allow_local_asr)
    t0 = time.monotonic()

    async with AsyncSessionLocal() as session:
        track = await session.get(Track, track_id)
        if not track or not track.is_active:
            await _finalise(
                progress_id,
                "error",
                log_line=("[catalog_only] ERROR: track not found"),
            )
            return {
                "status": "error",
                "detail": "track_not_found",
            }

        job = None
        if job_id:
            from app.repositories.audio_compute import (
                AudioComputeRepository,
            )

            repo = AudioComputeRepository(session)
            job = await repo.get_job(job_id)

        artist = track.artist or ""
        title = track.title or ""

        if not bypass_cache:
            for cache_artist, cache_title, _mode in _lyrics_search_attempts(
                artist, title
            ):
                cached = await get_cached_lyrics_result(
                    cache_artist, cache_title
                )
                if _cached_satisfies_request(cached, with_sync):
                    if job is not None:
                        await _save_catalog_result_and_close(
                            session,
                            job=job,
                            payload=cached,
                            progress_id=progress_id,
                            with_sync=with_sync,
                        )
                        await session.commit()
                    else:
                        repo_l = LyricsRepository(session)
                        await repo_l.create_or_update(
                            track_id=track_id,
                            plain_text=cached["text"],
                            source="auto",
                            synced_lines=(
                                cached.get("synced_lines")
                                if with_sync
                                else None
                            ),
                            sync_quality=cached.get("sync_quality"),
                            sync_profile=cached.get("sync_profile"),
                            source_name=cached.get("source_name"),
                        )
                        await session.commit()
                    await _finalise(
                        progress_id,
                        "found",
                        log_line=("[catalog_only] cache hit"),
                    )
                    return {
                        "status": "found",
                        "from": "cache",
                    }

        audio_path: str | None = None
        tmp_dir: str | None = None
        try:
            if use_local_asr and (
                track.file_key or getattr(track, "sc_url", None)
            ):
                tmp_dir = tempfile.mkdtemp()
                audio_path = await _fetch_audio_to_file(
                    track, tmp_dir, session
                )
                logger.warning(
                    "lyrics_local_asr_dev_escape",
                    track_id=track_id,
                )

            try:
                gen_result = await asyncio.wait_for(
                    asyncio.to_thread(
                        generate_lyrics,
                        artist,
                        title,
                        audio_path,
                        None,
                        None,
                        external_id=track.external_id,
                        disable_local_asr=(not use_local_asr),
                    ),
                    timeout=float(settings.lyrics_provider_timeout_seconds),
                )
            except asyncio.TimeoutError:
                gen_result = None
                logger.warning(
                    "catalog_only_timeout",
                    track_id=track_id,
                )
            except TypeError:
                gen_result = await asyncio.wait_for(
                    asyncio.to_thread(
                        _call_provider,
                        generate_lyrics,
                        artist=artist,
                        title=title,
                        audio_path=audio_path,
                        on_progress=None,
                        on_cancel=None,
                        external_id=track.external_id,
                    ),
                    timeout=float(settings.lyrics_provider_timeout_seconds),
                )

            elapsed_ms = int((time.monotonic() - t0) * 1000)

            if gen_result is None:
                if job is not None:
                    from app.services.lyrics_cascade import (
                        handle_tier_miss,
                    )

                    will_fallback = await handle_tier_miss(
                        session,
                        job=job,
                        reason="catalog_miss",
                        with_sync=with_sync,
                        bypass_cache=bypass_cache,
                    )
                    await session.commit()
                    if will_fallback:
                        logger.info(
                            "catalog_only_miss_fallback",
                            job_id=job.id,
                            elapsed_ms=elapsed_ms,
                        )
                        return {
                            "status": "fallback",
                        }
                await _finalise(
                    progress_id,
                    "not_found",
                    log_line=("[catalog_only] no lyrics found"),
                )
                return {"status": "not_found"}

            payload = _result_to_payload(gen_result)
            if with_sync and not _payload_has_non_empty_synced(
                payload
            ):
                if job is not None:
                    # Pre-save catalog text so ``remote_whisper`` can
                    # align ASR word timings to Genius/etc. in
                    # :func:`job_result` (PrivateCore opcode aligner).
                    if (payload.get("text") or "").strip():
                        try:
                            repo_pre = LyricsRepository(session)
                            await repo_pre.create_or_update(
                                track_id=track_id,
                                plain_text=payload["text"],
                                source="auto",
                                synced_lines=None,
                                sync_quality=None,
                                sync_profile=None,
                                source_name=payload.get(
                                    "source_name"
                                ),
                            )
                        except Exception:
                            logger.debug(
                                "lyrics_pre_save_before_remote_failed",
                                track_id=track_id,
                            )
                    from app.services.lyrics_cascade import (
                        handle_tier_miss,
                    )

                    will_fallback = await handle_tier_miss(
                        session,
                        job=job,
                        reason=(
                            "catalog_plain_text_no_synced_lines"
                        ),
                        with_sync=with_sync,
                        bypass_cache=bypass_cache,
                    )
                    await session.commit()
                    if will_fallback:
                        logger.info(
                            "catalog_only_sync_unsatisfied_fallback",
                            job_id=job.id,
                        )
                        return {
                            "status": "fallback",
                        }
                    await _finalise(
                        progress_id,
                        "not_found",
                        log_line=(
                            "[catalog_only] with_sync: no timed lines "
                            "and cascade has no further tier"
                        ),
                    )
                    return {
                        "status": "not_found",
                    }
                await _finalise(
                    progress_id,
                    "not_found",
                    log_line=(
                        "[catalog_only] with_sync needs timed lines; "
                        "catalog has plain text only"
                    ),
                )
                return {
                    "status": "not_found",
                }
            try:
                await set_cached_lyrics_result(artist, title, payload)
            except Exception:
                logger.debug(
                    "catalog_only_cache_write_failed",
                    track_id=track_id,
                )

            if job is not None:
                await _save_catalog_result_and_close(
                    session,
                    job=job,
                    payload=payload,
                    progress_id=progress_id,
                    with_sync=with_sync,
                )
                await session.commit()
            else:
                repo_l = LyricsRepository(session)
                await repo_l.create_or_update(
                    track_id=track_id,
                    plain_text=payload["text"],
                    source="auto",
                    synced_lines=(
                        payload["synced_lines"] if with_sync else None
                    ),
                    sync_quality=payload.get("sync_quality"),
                    sync_profile=payload.get("sync_profile"),
                    source_name=payload.get("source_name"),
                )
                await session.commit()
            await _finalise(
                progress_id,
                "found",
                log_line=(
                    f"[catalog_only] saved (chars="
                    f"{len(payload['text'])},"
                    f" sync={payload['synced_lines'] is not None})"
                ),
            )
            return {
                "status": "found",
                "from": "catalog",
            }
        except Exception as exc:
            logger.exception(
                "catalog_only_failed",
                track_id=track_id,
            )
            if job is not None:
                from app.services.lyrics_cascade import (
                    handle_tier_failure,
                )

                will_fallback = await handle_tier_failure(
                    session,
                    job=job,
                    reason=f"catalog_only_exception:{exc}",
                    with_sync=with_sync,
                    bypass_cache=bypass_cache,
                )
                await session.commit()
                if will_fallback:
                    return {"status": "fallback"}
            await _finalise(
                progress_id,
                "error",
                log_line=(f"[catalog_only] ERROR: {exc}"),
            )
            return {"status": "error"}
        finally:
            if tmp_dir and os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)


@broker.task
async def speechkit_lyrics_task(
    track_id: int,
    with_sync: bool = False,
    progress_id: str = "",
    bypass_cache: bool = False,
    job_id: str = "",
) -> dict:
    """Tier 3: paid Yandex SpeechKit fallback.

    Hands the track audio to Yandex Cloud SpeechKit Async
    Recognition. Budget guard, cost accounting, and disabled-flag
    handling all live in the adapter module.
    """
    from app.services.asr_speechkit_adapter import (
        SpeechKitBudgetExhausted,
        SpeechKitDisabled,
        SpeechKitError,
        transcribe as speechkit_transcribe,
    )

    structlog.contextvars.bind_contextvars(
        track_id=track_id,
        progress_id=progress_id,
        correlation_id=job_id or progress_id,
        tier="speechkit_paid",
    )
    logger.info(
        "speechkit_task_started",
        track_id=track_id,
        job_id=job_id,
    )

    async with AsyncSessionLocal() as session:
        track = await session.get(Track, track_id)
        if not track or not track.is_active:
            await _finalise(
                progress_id,
                "error",
                log_line="[speechkit] track not found",
            )
            return {
                "status": "error",
                "detail": "track_not_found",
            }
        if not track.file_key and not getattr(
            track, "sc_url", None
        ):
            await _finalise(
                progress_id,
                "error",
                log_line="[speechkit] track has no audio",
            )
            return {
                "status": "error",
                "detail": "no_audio",
            }

        job = None
        if job_id:
            from app.repositories.audio_compute import (
                AudioComputeRepository,
            )

            repo = AudioComputeRepository(session)
            job = await repo.get_job(job_id)

        presigned: str | None = None
        if track.file_key:
            try:
                presigned = await s3.get_presigned_url(
                    track.file_key
                )
            except Exception as exc:
                await _finalise(
                    progress_id,
                    "error",
                    log_line=(
                        f"[speechkit] presign failed: {exc}"
                    ),
                )
                return {"status": "error"}
        else:
            from app.config import settings
            from app.services.soundcloud_service import (
                SoundCloudService,
            )

            if not settings.sc_client_id:
                await _finalise(
                    progress_id,
                    "error",
                    log_line=(
                        "[speechkit] SoundCloud is not "
                        "configured (no SC_CLIENT_ID)"
                    ),
                )
                return {"status": "error", "detail": "no_sc"}
            try:
                sc = SoundCloudService(
                    settings.sc_client_id, session
                )
                presigned, _ = await sc.get_stream_info(
                    track.sc_url
                )
            except Exception as exc:
                await _finalise(
                    progress_id,
                    "error",
                    log_line=(
                        f"[speechkit] SC stream URL failed: {exc}"
                    ),
                )
                return {"status": "error"}

        try:
            audio_seconds = float(
                getattr(track, "duration_seconds", 0) or 0
            )
        except Exception:
            audio_seconds = 0.0

        try:
            result = await speechkit_transcribe(
                presigned,
                audio_seconds=audio_seconds,
                correlation_id=job_id or progress_id,
            )
        except (
            SpeechKitDisabled,
            SpeechKitBudgetExhausted,
        ) as exc:
            if job is not None:
                from app.services.lyrics_cascade import (
                    handle_tier_failure,
                )

                will_fallback = await handle_tier_failure(
                    session,
                    job=job,
                    reason=str(exc),
                    with_sync=with_sync,
                    bypass_cache=bypass_cache,
                )
                await session.commit()
                if will_fallback:
                    return {"status": "fallback"}
            await _finalise(
                progress_id,
                "error",
                log_line=(
                    f"[speechkit] gated: {exc}"
                ),
            )
            return {
                "status": "error",
                "detail": str(exc),
            }
        except SpeechKitError as exc:
            logger.exception(
                "speechkit_transcribe_failed",
                job_id=job_id,
            )
            if job is not None:
                from app.services.lyrics_cascade import (
                    handle_tier_failure,
                )

                will_fallback = await handle_tier_failure(
                    session,
                    job=job,
                    reason=f"speechkit_error:{exc}",
                    with_sync=with_sync,
                    bypass_cache=bypass_cache,
                )
                await session.commit()
                if will_fallback:
                    return {"status": "fallback"}
            await _finalise(
                progress_id,
                "error",
                log_line=(
                    f"[speechkit] error: {exc}"
                ),
            )
            return {"status": "error"}

        synced_dicts: list[dict] | None = None
        if with_sync and result.get("synced_lines"):
            synced_dicts = result["synced_lines"]

        repo_l = LyricsRepository(session)
        await repo_l.create_or_update(
            track_id=track_id,
            plain_text=result["plain_text"],
            source="auto",
            synced_lines=synced_dicts,
            sync_quality=result.get("sync_quality"),
            sync_profile=result.get("sync_profile"),
        )
        if job is not None:
            from datetime import datetime, timezone

            _close_job_attempt(job, status="success")
            job.status = "done"
            job.finished_at = datetime.now(timezone.utc)
            started = job.started_at or job.created_at
            if started:
                if started.tzinfo is None:
                    started = started.replace(
                        tzinfo=timezone.utc
                    )
                duration = (
                    datetime.now(timezone.utc) - started
                ).total_seconds()
                job.duration_ms = int(duration * 1000)
                try:
                    from app.core.observability import (
                        lyrics_job_observed,
                    )

                    lyrics_job_observed(
                        tier="speechkit_paid",
                        status="success",
                        duration_seconds=duration,
                    )
                except Exception:
                    pass
        await session.commit()
        await _finalise(
            progress_id,
            "found",
            log_line=(
                "[speechkit] lyrics saved "
                f"(cost={result.get('cost_rub')}rub)"
            ),
        )
        return {
            "status": "found",
            "cost_rub": result.get("cost_rub"),
        }
