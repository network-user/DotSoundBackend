"""Daily orphan sweep for content-addressed audio blobs and HLS bundles.

Three classes of debris can build up around the CAS store:

1. ``audio_blobs`` rows with ``ref_count <= 0`` that were not deleted
   inline (e.g. crash between ``ref_count--`` and ``DELETE``).
2. S3 objects under ``blobs/`` that no row references at all (orphans
   from a failed transcode, manual upload, etc.).
3. S3 prefixes under ``hls-blobs/`` whose source hash is not referenced
   by any active AudioBlob.

The worker is safety-gated by a minimum-age window so we never delete
an object that a concurrent transcode is in the middle of writing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select

from app.config import settings
from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.audio_blob import AudioBlob

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_MIN_AGE_HOURS = 6
_BLOB_PREFIX = "blobs/"
_HLS_BLOB_PREFIX = "hls-blobs/"


def _key_age(last_modified: datetime, now: datetime) -> timedelta:
    if last_modified.tzinfo is None:
        last_modified = last_modified.replace(tzinfo=UTC)
    return now - last_modified


async def _list_keys(
    prefix: str,
) -> list[tuple[str, datetime]]:
    out: list[tuple[str, datetime]] = []
    cont_token: str | None = None
    async with s3.get_s3_client() as client:
        while True:
            kwargs: dict[str, Any] = {
                "Bucket": settings.minio_bucket,
                "Prefix": prefix,
            }
            if cont_token:
                kwargs["ContinuationToken"] = cont_token
            resp: dict[str, Any] = await client.list_objects_v2(**kwargs)
            for obj in resp.get("Contents") or ():
                out.append((obj["Key"], obj["LastModified"]))
            if not resp.get("IsTruncated"):
                break
            cont_token = resp.get("NextContinuationToken")
    return out


async def _drop_zero_ref_blob_rows() -> int:
    """Delete audio_blobs rows whose ref_count fell to zero and the S3 key."""
    deleted = 0
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(AudioBlob).where(AudioBlob.ref_count <= 0)
        )
        rows = list(res.scalars().all())
        for row in rows:
            try:
                await s3.delete_object(row.s3_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "blob_gc_s3_delete_failed",
                    s3_key=row.s3_key,
                    error=str(exc),
                )
            if row.hls_manifest_key:
                hls_prefix = _hls_prefix_for_manifest(row.hls_manifest_key)
                if hls_prefix:
                    try:
                        await s3.delete_objects_by_prefix(hls_prefix)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "blob_gc_hls_prefix_delete_failed",
                            prefix=hls_prefix,
                            error=str(exc),
                        )
            await session.delete(row)
            deleted += 1
        await session.commit()
    return deleted


def _hls_prefix_for_manifest(manifest_key: str) -> str | None:
    if not manifest_key.startswith(_HLS_BLOB_PREFIX):
        return None
    if not manifest_key.endswith("/master.m3u8"):
        return None
    return manifest_key.removesuffix("/master.m3u8") + "/"


async def _sweep_orphan_audio_keys(now: datetime) -> int:
    """Delete blobs/* keys that no audio_blobs row references."""
    keys = await _list_keys(_BLOB_PREFIX)
    if not keys:
        return 0
    referenced: set[str] = set()
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(AudioBlob.s3_key))
        referenced = {str(row[0]) for row in res.all()}

    deleted = 0
    cutoff = timedelta(hours=_MIN_AGE_HOURS)
    for key, last_modified in keys:
        if key in referenced:
            continue
        if _key_age(last_modified, now) < cutoff:
            continue
        try:
            await s3.delete_object(key)
            deleted += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "blob_gc_orphan_audio_delete_failed",
                key=key,
                error=str(exc),
            )
    return deleted


async def _sweep_orphan_hls_prefixes(now: datetime) -> int:
    """Delete hls-blobs/{xx}/{sha}/... groups not referenced by any blob."""
    keys = await _list_keys(_HLS_BLOB_PREFIX)
    if not keys:
        return 0

    grouped: dict[str, list[tuple[str, datetime]]] = {}
    for key, last_modified in keys:
        rest = key[len(_HLS_BLOB_PREFIX):]
        parts = rest.split("/", 2)
        if len(parts) < 3:
            continue
        group = f"{_HLS_BLOB_PREFIX}{parts[0]}/{parts[1]}/"
        grouped.setdefault(group, []).append((key, last_modified))

    if not grouped:
        return 0

    referenced_groups: set[str] = set()
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(AudioBlob.hls_manifest_key).where(
                AudioBlob.hls_manifest_key.isnot(None)
            )
        )
        for (manifest_key,) in res.all():
            prefix = _hls_prefix_for_manifest(str(manifest_key))
            if prefix:
                referenced_groups.add(prefix)

    deleted_groups = 0
    cutoff = timedelta(hours=_MIN_AGE_HOURS)
    for group, members in grouped.items():
        if group in referenced_groups:
            continue
        newest = max(m for _, m in members)
        if _key_age(newest, now) < cutoff:
            continue
        try:
            n = await s3.delete_objects_by_prefix(group)
            if n:
                deleted_groups += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "blob_gc_orphan_hls_delete_failed",
                prefix=group,
                error=str(exc),
            )
    return deleted_groups


@broker.task
async def gc_audio_blobs_task() -> dict[str, Any]:
    """Daily reconciliation between audio_blobs / S3 / HLS prefixes."""
    now = datetime.now(UTC)
    zero_ref_rows = await _drop_zero_ref_blob_rows()
    orphan_audio = await _sweep_orphan_audio_keys(now)
    orphan_hls = await _sweep_orphan_hls_prefixes(now)
    summary = {
        "zero_ref_rows": zero_ref_rows,
        "orphan_audio_keys": orphan_audio,
        "orphan_hls_groups": orphan_hls,
    }
    logger.info("audio_blob_gc_complete", **summary)
    return summary
