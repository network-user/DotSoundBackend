"""Batch sweep that re-encodes legacy track covers under the current
cover defaults (``image_cover_max_size``, ``image_quality``,
``image_thumbnail_size``).

Two tasks live here:

1. ``regen_covers_sweep_task`` -- paginated worker. Picks up where the
   previous run left off via a Redis cursor (``cover_regen:cursor``),
   re-encodes each cover under a fresh UUID key, updates
   ``tracks.cover_key`` and schedules the old keys for delayed delete.
2. ``regen_covers_gc_task`` -- drains the delete-scheduled queue
   (``cover_regen:gc:keys``, ZSET keyed by expiry epoch) once entries
   pass their grace window.

Both tasks are no-op unless ``settings.cover_regen_enabled`` is True.
Per-track Redis locks (``cover_regen:lock:{track_id}``) prevent two
sweeps from re-encoding the same track at the same time.
"""

from __future__ import annotations

import contextlib
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from botocore.exceptions import ClientError
from redis.asyncio import Redis

from app.config import settings
from app.core import observability, s3
from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.core.tkq import broker
from app.repositories.track import TrackRepository
from app.services import cover_regen_adapter
from app.services.media_service import (
    create_thumbnail,
    strip_metadata_and_compress,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_CURSOR_KEY = "cover_regen:cursor"
_LOCK_KEY_PREFIX = "cover_regen:lock:"
_GC_ZSET_KEY = "cover_regen:gc:keys"
_COVERS_PREFIX = "covers/"
_THUMB_SUFFIX = "_thumb.webp"


def _split_cover_key(cover_key: str) -> tuple[str, str] | None:
    parts = cover_key.split("/")
    if len(parts) < 3 or parts[0] != "covers":
        return None
    owner = parts[1]
    tail = "/".join(parts[2:])
    return owner, tail


def _thumb_key_for(cover_key: str) -> str | None:
    if not cover_key.endswith(".webp"):
        return None
    return cover_key[: -len(".webp")] + _THUMB_SUFFIX


def _build_new_keys(owner: str) -> tuple[str, str]:
    new_uuid = uuid.uuid4().hex
    img_key = f"covers/{owner}/{new_uuid}.webp"
    thumb_key = f"covers/{owner}/{new_uuid}{_THUMB_SUFFIX}"
    return img_key, thumb_key


async def _schedule_delete(redis: Redis, *keys: str) -> None:
    if not keys:
        return
    expiry = time.time() + settings.cover_regen_grace_seconds
    mapping = {key: expiry for key in keys if key}
    if mapping:
        await redis.zadd(_GC_ZSET_KEY, mapping)


async def _try_acquire_lock(redis: Redis, track_id: int) -> bool:
    key = f"{_LOCK_KEY_PREFIX}{track_id}"
    return bool(
        await redis.set(
            key,
            "1",
            nx=True,
            ex=settings.cover_regen_lock_ttl_seconds,
        )
    )


async def _release_lock(redis: Redis, track_id: int) -> None:
    key = f"{_LOCK_KEY_PREFIX}{track_id}"
    with contextlib.suppress(Exception):
        await redis.delete(key)


async def _process_one(
    track_id: int,
    cover_key: str,
    updated_at: datetime | None,
    now: datetime,
) -> tuple[bool, int]:
    """Returns (processed, bytes_saved)."""
    if not cover_key.startswith(_COVERS_PREFIX):
        observability.cover_regen_skipped_observed(reason="not_covers_prefix")
        return False, 0
    split = _split_cover_key(cover_key)
    if split is None:
        observability.cover_regen_skipped_observed(reason="bad_path")
        return False, 0
    owner, _ = split

    if not cover_regen_adapter.should_regen_cover(
        cover_key=cover_key,
        updated_at=updated_at,
        now=now,
    ):
        observability.cover_regen_skipped_observed(reason="policy")
        return False, 0

    try:
        raw = await s3.download_object(cover_key)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("404", "NoSuchKey", "NotFound"):
            logger.info(
                "cover_regen_missing_source",
                track_id=track_id,
                cover_key=cover_key,
            )
            observability.cover_regen_skipped_observed(reason="missing_source")
            return False, 0
        raise

    original_size = len(raw)
    processed, _, _ = strip_metadata_and_compress(
        raw,
        max_size=settings.image_cover_max_size,
        quality=settings.image_quality,
    )
    thumb = create_thumbnail(
        processed,
        size=settings.image_thumbnail_size,
    )

    new_cover_key, new_thumb_key = _build_new_keys(owner)
    await s3.upload_object(new_cover_key, processed, "image/webp")
    await s3.upload_object(new_thumb_key, thumb, "image/webp")

    async with AsyncSessionLocal() as session:
        repo = TrackRepository(session)
        updated = await repo.swap_cover_key_if_unchanged(
            track_id=track_id,
            old_cover_key=cover_key,
            new_cover_key=new_cover_key,
        )
        if updated:
            await session.commit()
        else:
            await session.rollback()

    if not updated:
        logger.info(
            "cover_regen_skipped_concurrent_change",
            track_id=track_id,
            cover_key=cover_key,
        )
        observability.cover_regen_skipped_observed(reason="concurrent_change")
        for stale_key in (new_cover_key, new_thumb_key):
            try:
                await s3.delete_object(stale_key)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "cover_regen_rollback_delete_failed",
                    track_id=track_id,
                    stale_key=stale_key,
                )
        return False, 0

    redis = get_redis_client()
    old_thumb = _thumb_key_for(cover_key) or ""
    await _schedule_delete(redis, cover_key, old_thumb)

    saved = max(0, original_size - len(processed))
    logger.info(
        "cover_regen_processed",
        track_id=track_id,
        old_key=cover_key,
        new_key=new_cover_key,
        original_bytes=original_size,
        result_bytes=len(processed),
        bytes_saved=saved,
    )
    observability.cover_regen_processed_observed(bytes_saved=saved)
    return True, saved


@broker.task
async def regen_covers_sweep_task() -> dict[str, Any]:
    """Process one batch of cover_keys above the saved Redis cursor."""
    if not settings.cover_regen_enabled:
        return {"skipped": True, "reason": "disabled"}

    redis = get_redis_client()
    raw_cursor = await redis.get(_CURSOR_KEY)
    try:
        cursor = int(raw_cursor) if raw_cursor else 0
    except (TypeError, ValueError):
        cursor = 0

    async with AsyncSessionLocal() as session:
        repo = TrackRepository(session)
        rows = await repo.list_covers_above_id(
            cursor=cursor,
            limit=settings.cover_regen_batch_size,
        )

    if not rows:
        await redis.set(_CURSOR_KEY, "0")
        logger.info("cover_regen_sweep_exhausted", cursor=cursor)
        return {"processed": 0, "exhausted": True}

    now = datetime.now(UTC)
    processed = 0
    skipped = 0
    failed = 0
    total_saved = 0

    for track_id, cover_key, updated_at in rows:
        if not await _try_acquire_lock(redis, track_id):
            skipped += 1
            observability.cover_regen_skipped_observed(reason="locked")
            continue
        try:
            ok, saved = await _process_one(
                track_id=track_id,
                cover_key=cover_key,
                updated_at=updated_at,
                now=now,
            )
            if ok:
                processed += 1
                total_saved += saved
            else:
                skipped += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            observability.cover_regen_failed_observed()
            logger.exception(
                "cover_regen_failed",
                track_id=track_id,
                error=str(exc),
            )
        finally:
            await _release_lock(redis, track_id)

    new_cursor = rows[-1][0]
    await redis.set(_CURSOR_KEY, str(new_cursor))

    summary = {
        "batch_size": len(rows),
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "bytes_saved": total_saved,
        "cursor_from": cursor,
        "cursor_to": new_cursor,
    }
    logger.info("cover_regen_sweep_complete", **summary)
    return summary


@broker.task
async def regen_covers_gc_task() -> dict[str, Any]:
    """Delete legacy cover/thumb keys whose grace window has passed."""
    if not settings.cover_regen_enabled:
        return {"skipped": True, "reason": "disabled"}

    redis = get_redis_client()
    cutoff = time.time()
    expired = await redis.zrangebyscore(
        _GC_ZSET_KEY,
        min=0,
        max=cutoff,
    )

    deleted = 0
    failed = 0
    for raw_key in expired:
        key = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
        try:
            await s3.delete_object(key)
            deleted += 1
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchKey", "NotFound"):
                deleted += 1
            else:
                failed += 1
                logger.warning(
                    "cover_regen_gc_delete_failed",
                    key=key,
                    code=code,
                )
                continue
        except Exception as exc:  # noqa: BLE001
            failed += 1
            logger.warning(
                "cover_regen_gc_delete_failed",
                key=key,
                error=str(exc),
            )
            continue
        await redis.zrem(_GC_ZSET_KEY, raw_key)

    summary = {
        "deleted": deleted,
        "failed": failed,
        "remaining": await redis.zcard(_GC_ZSET_KEY),
    }
    logger.info("cover_regen_gc_complete", **summary)
    return summary
