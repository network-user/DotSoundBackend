"""Backfill `tracks.blob_id` and `audio_blobs` for existing in-bucket UGC.

Streams each `file_key` from S3, content-addresses bytes, links the track, and
optionally removes the previous object when its key was not already CAS.

Runbook:
- Take a DB backup before running in production.
- Run during low traffic; the script processes rows one at a time.

Environment:
- `DOTSOUND_ALLOW_BLOB_BACKFILL=1` must be set (safety guard).

Usage:
    DOTSOUND_ALLOW_BLOB_BACKFILL=1 poetry run python scripts/backfill_audio_blobs.py
"""

import asyncio
import mimetypes
import os
from os.path import splitext

import structlog
from sqlalchemy import select

from app.core import s3
from app.core.db import AsyncSessionLocal
from app.models.track import Track
from app.services.audio_blob_service import AudioBlobService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)
_UGC_SOURCES = frozenset(
    {
        "internal",
        "telegram",
    }
)


def _ext_from_key(file_key: str) -> str:
    _base, ext = splitext(
        str(file_key or "").rstrip("/")
    )
    e = (ext or "").lstrip(".") or "bin"
    if len(e) > 10:
        return "bin"
    return e


def _guess_ct(file_key: str) -> str:
    ct, _ = mimetypes.guess_type(
        f"x.{_ext_from_key(file_key)}"
    )
    return ct or "audio/mpeg"


async def main() -> None:
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Track.id).where(
                Track.file_key.isnot(None),
                Track.blob_id.is_(None),
                Track.is_active.is_(True),
                Track.source.in_(_UGC_SOURCES),
            )
        )
        ids: list[int] = [i for (i,) in res.all()]

    logger.info("backfill_audio_blobs_start", count=len(ids))
    for tid in ids:
        async with AsyncSessionLocal() as session:
            t = await session.get(Track, tid)
            if t is None or t.blob_id is not None or not t.file_key:
                continue
            data = await s3.download_object(t.file_key)
            ext = _ext_from_key(t.file_key)
            ct = _guess_ct(t.file_key)
            svc = AudioBlobService(session)
            ab, _ = await svc.get_or_create_from_bytes(
                data, ext, ct
            )
            old_key = t.file_key
            await svc.attach_playback_blob(t, ab)
            await session.commit()
        if old_key and old_key != ab.s3_key:
            try:
                await s3.delete_object(old_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "backfill_delete_legacy_key_failed",
                    key=old_key,
                    error=str(exc),
                )
        logger.info(
            "backfill_track",
            track_id=tid,
            sha=ab.content_sha256,
        )
    logger.info("backfill_audio_blobs_done")


if __name__ == "__main__":
    if os.environ.get("DOTSOUND_ALLOW_BLOB_BACKFILL") != "1":
        raise SystemExit(
            "Set DOTSOUND_ALLOW_BLOB_BACKFILL=1 to run this job."
        )
    asyncio.run(main())
