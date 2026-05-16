"""Background migration of legacy 10s-segment HLS bundles to 4s.

The HLS streaming policy in PrivateCore advertises a target segment
duration; older transcoder runs produced 10-second TS segments,
which forces hls.js to wait one full segment (~10 s) before reaching
``canplay``. This worker walks the back catalogue in small batches,
re-runs ``transcode_hls_only`` so each track gets a fresh, short-
segment bundle, and stamps the new ``hls_bundle_version`` column.

Pacing is deliberately conservative: we sleep
``HLS_MIGRATE_INTER_TASK_SECONDS`` between tracks so the FFmpeg
subprocesses cannot saturate a single CPU and starve playback
streaming on the same host. Admin-triggered runs honour an explicit
``limit`` so an operator can prove out the migration on a small
slice before scaling up.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog
from dotsound_private_core.services.playback_streaming_policy import (
    HLS_MIGRATE_BATCH_SIZE,
    HLS_MIGRATE_INTER_TASK_SECONDS,
    LATEST_BUNDLE_VERSION,
    is_bundle_outdated,
)
from sqlalchemy import or_, select

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.audio_blob import AudioBlob
from app.models.track import Track
from app.services.transcoding import transcode_hls_only

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _select_outdated_track_ids(
    session: AsyncSession,
    *,
    limit: int,
) -> list[int]:
    stmt = (
        select(Track.id)
        .where(
            Track.hls_manifest_key.is_not(None),
            Track.is_active.is_(True),
            or_(
                Track.hls_bundle_version.is_(None),
                Track.hls_bundle_version < LATEST_BUNDLE_VERSION,
            ),
        )
        .order_by(Track.id.asc())
        .limit(max(1, limit))
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def _resolve_source_for_track(
    session: AsyncSession,
    track: Track,
) -> tuple[str, str | None] | None:
    """Return (mp3_file_key, source_sha256) for a single track.

    The migration prefers re-encoding from the canonical AudioBlob
    (one CAS row per source SHA-256) so an entire family of tracks
    sharing the same source converges on the same migrated bundle.
    Falls back to the per-track ``file_key`` for legacy rows that
    pre-date the AudioBlob CAS layer.
    """
    if track.blob_id is not None:
        blob = await session.get(AudioBlob, track.blob_id)
        if blob and blob.s3_key:
            return blob.s3_key, getattr(blob, "source_sha256", None)
    if track.file_key:
        return track.file_key, track.source_sha256
    return None


async def migrate_one_track(track_id: int) -> bool:
    """Re-transcode a single track's HLS bundle to the latest version.

    Returns ``True`` if a migration was attempted (i.e. transcoder
    enqueued), ``False`` when the track is already on the latest
    bundle layout or has no source MP3 to re-encode from.
    """
    async with AsyncSessionLocal() as session:
        track = await session.get(Track, track_id)
        if track is None:
            return False
        if not is_bundle_outdated(track.hls_bundle_version):
            return False
        if not track.is_active or not track.hls_manifest_key:
            return False
        resolved = await _resolve_source_for_track(session, track)
        if resolved is None:
            logger.info(
                "hls_migrate_skip_no_source",
                track_id=track_id,
            )
            return False
        file_key, source_sha256 = resolved

    await transcode_hls_only(
        track_id,
        file_key,
        source_sha256=source_sha256,
    )
    return True


@broker.task
async def migrate_track_hls(track_id: int) -> None:
    """Taskiq entry-point used by admin batch enqueue."""
    try:
        await migrate_one_track(track_id)
    except Exception:
        logger.exception("hls_migrate_task_failed", track_id=track_id)


async def enqueue_migration_batch(
    *,
    limit: int = HLS_MIGRATE_BATCH_SIZE,
) -> int:
    """Pick up to ``limit`` outdated tracks and enqueue one task each.

    Returns the number of tasks scheduled. The caller (admin route /
    cron seed) controls cadence; we never block on the actual ffmpeg
    work. Pacing between tracks happens worker-side via
    :func:`HLS_MIGRATE_INTER_TASK_SECONDS`.
    """
    bound = max(1, min(int(limit), HLS_MIGRATE_BATCH_SIZE * 16))
    async with AsyncSessionLocal() as session:
        ids = await _select_outdated_track_ids(session, limit=bound)
    scheduled = 0
    for tid in ids:
        try:
            await migrate_track_hls.kiq(tid)
        except Exception:
            logger.exception("hls_migrate_enqueue_failed", track_id=tid)
            continue
        scheduled += 1
        if HLS_MIGRATE_INTER_TASK_SECONDS > 0:
            await asyncio.sleep(HLS_MIGRATE_INTER_TASK_SECONDS)
    if scheduled:
        logger.info(
            "hls_migrate_batch_enqueued",
            scheduled=scheduled,
            requested=bound,
        )
    return scheduled


async def count_outdated_tracks() -> int:
    """Operational metric: how many tracks still need migration."""
    from sqlalchemy import func

    async with AsyncSessionLocal() as session:
        stmt = select(func.count(Track.id)).where(
            Track.hls_manifest_key.is_not(None),
            Track.is_active.is_(True),
            or_(
                Track.hls_bundle_version.is_(None),
                Track.hls_bundle_version < LATEST_BUNDLE_VERSION,
            ),
        )
        result = await session.execute(stmt)
        return int(result.scalar_one())
