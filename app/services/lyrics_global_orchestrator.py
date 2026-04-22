"""Global post-import lyrics orchestrator.

Stage 3 of the concurrency hardening plan. The per-job orchestrator
in :mod:`app.services.import_lyrics_worker` paces lyrics fetches
*within* a single job, but every parallel job multiplies the load
on the upstream lyrics provider. This module replaces that with a
single shared queue + a single pacing loop, so 100 parallel
imports apply the same delay budget as one big import would.

Activated by :pyattr:`AppSettings.lyrics_global_orchestrator_enabled`
(defaults to True). When disabled, falls back to the legacy
per-job pacing in ``import_lyrics_worker``.

The orchestrator reuses the existing pacing knobs:

* ``yandex_music_import_lyrics_delay_min_seconds``
* ``yandex_music_import_lyrics_delay_max_seconds``
* ``yandex_music_import_lyrics_cooldown_seconds`` — applied after
  a block signal from the upstream proxy pool
* ``lyrics_global_max_consecutive_blocks`` — how many block
  signals trigger an emergency long cooldown (one round of the
  loop will skip work and sleep for the full cooldown)
"""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass

import structlog
from taskiq import TaskiqEvents, TaskiqState

from app.config import settings
from app.core.redis import get_redis_client
from app.core.tkq import broker

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


_orchestrator_task: asyncio.Task | None = None

_BLOCK_MARKERS: tuple[str, ...] = (
    "captcha",
    "pool_exhaust",
    "exhausted",
)


@dataclass(frozen=True)
class _QueueItem:
    track_id: int
    with_sync: bool


def _serialize(item: _QueueItem) -> str:
    return json.dumps(
        {
            "track_id": int(item.track_id),
            "with_sync": bool(item.with_sync),
        }
    )


def _deserialize(raw: str | bytes) -> _QueueItem | None:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    track_id = data.get("track_id")
    with_sync = data.get("with_sync")
    if not isinstance(track_id, int):
        return None
    return _QueueItem(
        track_id=track_id,
        with_sync=bool(with_sync),
    )


async def enqueue(track_id: int, with_sync: bool) -> None:
    """Push a track onto the shared lyrics queue.

    Used by ``import_lyrics_worker.process_import_lyrics_task``
    when the global orchestrator is enabled. ``with_sync`` is
    forwarded verbatim to ``generate_lyrics_task``.
    """
    redis = get_redis_client()
    await redis.rpush(
        settings.lyrics_global_queue_key,
        _serialize(_QueueItem(track_id, with_sync)),
    )


def _pick_delay() -> float:
    lo = float(settings.yandex_music_import_lyrics_delay_min_seconds)
    hi = float(settings.yandex_music_import_lyrics_delay_max_seconds)
    if hi < lo:
        hi = lo
    return random.uniform(lo, hi)


def _is_block_signal(message: str | None) -> bool:
    if not message:
        return False
    lowered = message.lower()
    return any(marker in lowered for marker in _BLOCK_MARKERS)


def _peek_last_error() -> str | None:
    """Indirect read of the PrivateCore proxy-pool error state.

    Imported locally so the backend module-load graph stays clean
    of optional dependencies.
    """
    try:
        from dotsound_private_core.services import (  # noqa: PLC0415
            proxy_pool,
        )
    except ImportError:
        return None
    try:
        return proxy_pool.last_error()
    except Exception:  # noqa: BLE001
        return None


async def _process_one(item: _QueueItem) -> str:
    """Submit one track's lyrics generation. Returns a tag for
    pacing decisions: ``"normal"``, ``"skipped"`` (lock held),
    ``"blocked"`` (block signal seen after the kiq), or
    ``"error"`` (kiq failed).
    """
    from app.services.lyrics_worker import (
        TRACK_LOCK_KEY_PREFIX,
        generate_lyrics_task,
    )

    redis = get_redis_client()
    lock_held = await redis.exists(f"{TRACK_LOCK_KEY_PREFIX}{item.track_id}")
    if lock_held:
        logger.debug(
            "lyrics_global_skip_locked",
            track_id=item.track_id,
        )
        return "skipped"

    try:
        await generate_lyrics_task.kiq(
            item.track_id,
            with_sync=item.with_sync,
            progress_id="",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "lyrics_global_kiq_failed",
            track_id=item.track_id,
            error=str(exc),
        )
        return "error"

    last_error = _peek_last_error()
    if _is_block_signal(last_error):
        logger.warning(
            "lyrics_global_block_signal",
            track_id=item.track_id,
            last_error=last_error,
        )
        return "blocked"
    return "normal"


async def _orchestrator_loop() -> None:
    """Block on the shared queue, pace generate_lyrics_task kicks.

    Sleeps in three modes:

    * after a normal kick -> ``_pick_delay()``
    * after a block signal -> ``yandex_music_import_lyrics_cooldown_seconds``
    * after ``lyrics_global_max_consecutive_blocks`` consecutive
      blocks -> the same cooldown but counter is reset (we don't
      bail out forever, we just keep waiting that long between
      attempts until the upstream recovers).
    """
    redis = get_redis_client()
    consecutive_blocks = 0
    cooldown = float(settings.lyrics_global_block_cooldown_seconds)
    max_blocks = int(settings.lyrics_global_max_consecutive_blocks)
    while True:
        try:
            popped = await redis.blpop(
                [settings.lyrics_global_queue_key],
                timeout=30,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("lyrics_global_blpop_failed")
            await asyncio.sleep(5)
            continue
        if popped is None:
            continue

        _key, raw = popped
        item = _deserialize(raw)
        if item is None:
            logger.warning("lyrics_global_bad_queue_item", raw=str(raw))
            continue

        try:
            tag = await _process_one(item)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "lyrics_global_process_failed",
                track_id=item.track_id,
            )
            tag = "error"

        if tag == "blocked":
            consecutive_blocks += 1
        else:
            consecutive_blocks = 0

        if consecutive_blocks >= max_blocks:
            logger.warning(
                "lyrics_global_consecutive_blocks_cap",
                consecutive=consecutive_blocks,
                cooldown_seconds=cooldown,
            )
            consecutive_blocks = 0
            await asyncio.sleep(cooldown)
            continue
        if tag == "blocked":
            await asyncio.sleep(cooldown)
            continue
        if tag == "skipped":
            await asyncio.sleep(0.5)
            continue
        await asyncio.sleep(_pick_delay())


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start_orchestrator(_state: TaskiqState) -> None:
    if not settings.lyrics_global_orchestrator_enabled:
        logger.info("lyrics_global_orchestrator_disabled")
        return
    global _orchestrator_task
    if _orchestrator_task is None or _orchestrator_task.done():
        _orchestrator_task = asyncio.create_task(_orchestrator_loop())
        logger.info(
            "lyrics_global_orchestrator_started",
            queue_key=settings.lyrics_global_queue_key,
            delay_min=(settings.yandex_music_import_lyrics_delay_min_seconds),
            delay_max=(settings.yandex_music_import_lyrics_delay_max_seconds),
            cooldown=settings.lyrics_global_block_cooldown_seconds,
            max_consecutive_blocks=(
                settings.lyrics_global_max_consecutive_blocks
            ),
        )
