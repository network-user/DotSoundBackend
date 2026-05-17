"""Deferred post-import playback verification for SoundCloud tracks.

When SoundCloud tracks are imported via ``import_or_get_track`` with
``skip_playback_verify=True`` (e.g. from recommendation-discovery
imports), their IDs are written to the Redis sorted-set
``sc:unverified_imports`` with the import timestamp as score.

This worker sweeps that set every few minutes, picking up entries
that are:
- old enough to be worth checking  (>= sc_import_verify_delay_minutes)
- not yet expired from the window   (< sc_import_verify_ttl_minutes)

For each candidate it runs the full ``_resolve_third_party_stream``
check (same as ``_verify_imported_track_playback`` in
``SoundCloudService``).  Tracks that fail are suppressed when
``sc_strict_import_verify=True``, mirroring the behaviour that
would have occurred at import time.
"""

from __future__ import annotations

import time

import structlog
from fastapi import HTTPException

from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.core.tkq import broker
from app.models.track import Track

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_PENDING_VERIFY_ZSET = "sc:unverified_imports"


@broker.task
async def verify_pending_sc_imports_task(
    batch: int | None = None,
) -> dict:
    """Verify playback for SC tracks imported with skip_playback_verify=True.

    Safe to call concurrently: each member is removed from the ZSET
    immediately after processing so duplicate workers skip already-done
    entries.
    """
    from app.config import settings

    delay_s = settings.sc_import_verify_delay_minutes * 60
    ttl_s = settings.sc_import_verify_ttl_minutes * 60
    max_batch = int(batch or settings.sc_import_verify_batch)

    now = time.time()
    min_score = now - ttl_s
    max_score = now - delay_s

    redis = get_redis_client()
    await redis.zremrangebyscore(_PENDING_VERIFY_ZSET, 0, min_score)

    members: list[bytes | str] = await redis.zrangebyscore(
        _PENDING_VERIFY_ZSET,
        min_score,
        max_score,
        start=0,
        num=max_batch,
        withscores=False,
    )
    if not members:
        return {
            "status": "empty",
            "checked": 0,
            "ok": 0,
            "failed": 0,
            "skipped": 0,
        }

    ok = failed = skipped = 0
    for raw in members:
        member = raw.decode() if isinstance(raw, bytes) else raw
        track_id_str = member
        try:
            track_id = int(track_id_str)
        except ValueError:
            await redis.zrem(_PENDING_VERIFY_ZSET, member)
            skipped += 1
            continue

        try:
            outcome = await _verify_one(track_id, settings)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "sc_deferred_verify_unexpected_error",
                track_id=track_id,
                error=str(exc),
            )
            outcome = "skipped"

        await redis.zrem(_PENDING_VERIFY_ZSET, member)
        if outcome == "ok":
            ok += 1
        elif outcome == "failed":
            failed += 1
        else:
            skipped += 1

    logger.info(
        "sc_deferred_verify_sweep_done",
        checked=len(members),
        ok=ok,
        failed=failed,
        skipped=skipped,
    )
    return {
        "status": "done",
        "checked": len(members),
        "ok": ok,
        "failed": failed,
        "skipped": skipped,
    }


async def _verify_one(track_id: int, settings) -> str:
    async with AsyncSessionLocal() as session:
        row = await session.get(Track, track_id)
        if (
            row is None
            or not row.is_active
            or row.deleted_at is not None
        ):
            return "skipped"
        if row.access_mode != "third_party_stream" or not row.sc_url:
            return "skipped"

        from app.api.v1.tracks.playback import _resolve_third_party_stream
        from app.services.track_playback_health_service import (
            TrackPlaybackHealthService,
        )

        health = TrackPlaybackHealthService(session)
        try:
            await _resolve_third_party_stream(
                row, session, use_cache=False
            )
        except HTTPException as exc:
            detail = (
                exc.detail
                if isinstance(exc.detail, str)
                else str(exc.detail)
            )
            await health.record_import_verification_failed(
                track_id=track_id,
                viewer_user_id=row.uploaded_by_id,
                http_status=exc.status_code,
                detail=detail,
            )
            if settings.sc_strict_import_verify:
                from app.services.soundcloud_service import SoundCloudService

                sc_svc = SoundCloudService(settings.sc_client_id, session)
                await sc_svc._suppress_unverified_imported_track(
                    row, sc_data=None
                )
            else:
                await session.commit()
            logger.warning(
                "sc_deferred_verify_failed",
                track_id=track_id,
                http_status=exc.status_code,
                detail=detail[:120],
            )
            return "failed"
        except Exception as exc:  # noqa: BLE001
            detail = f"{type(exc).__name__}: {exc}"
            await health.record_import_verification_failed(
                track_id=track_id,
                viewer_user_id=row.uploaded_by_id,
                http_status=None,
                detail=detail,
            )
            await session.commit()
            logger.warning(
                "sc_deferred_verify_error",
                track_id=track_id,
                detail=detail[:120],
            )
            return "failed"

        await health.clear_failure_state(track_id)
        await session.commit()
        logger.info("sc_deferred_verify_ok", track_id=track_id)
        return "ok"
