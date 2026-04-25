from __future__ import annotations

import hashlib

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.models.image_blob import ImageBlob
from app.models.track import Track
from app.models.video_blob import VideoBlob

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class VideoBlobService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_from_bytes(
        self,
        data: bytes,
        extension: str,
        content_type: str,
    ) -> tuple[VideoBlob, bool]:
        """Return (row, created). `created` is True for a new DB row; False on reuse."""
        sha = _sha256_hex(data)
        res = await self._session.execute(
            select(VideoBlob).where(VideoBlob.content_sha256 == sha)
        )
        existing = res.scalars().first()
        if existing is not None:
            logger.debug("video_blob_dedup_hit", content_sha256=sha)
            return existing, False

        s3_key = await s3.put_cas_video(data, sha, extension, content_type)
        row = VideoBlob(
            content_sha256=sha,
            s3_key=s3_key,
            content_type=content_type,
            size_bytes=len(data),
            ref_count=0,
        )
        created = True
        async with self._session.begin_nested():
            self._session.add(row)
            try:
                await self._session.flush()
            except IntegrityError:
                created = False
        if not created:
            logger.debug(
                "video_blob_dedup_hit_race", content_sha256=sha
            )
            r2 = await self._session.execute(
                select(VideoBlob).where(VideoBlob.content_sha256 == sha)
            )
            return r2.scalars().one(), False

        logger.debug("video_blob_created", content_sha256=sha)
        return row, True

    async def attach_to_track(
        self, track: Track, blob: VideoBlob
    ) -> None:
        b = await self._session.get(VideoBlob, blob.id)
        if b is None:
            return
        b.ref_count = b.ref_count + 1
        track.video_key = b.s3_key
        track.video_blob_id = b.id
        await self._session.flush()

    async def set_thumbnail(
        self, blob: VideoBlob, thumb_blob: ImageBlob
    ) -> None:
        b = await self._session.get(VideoBlob, blob.id)
        if b is None:
            return
        b.thumbnail_blob_id = thumb_blob.id
        await self._session.flush()

    async def try_release_for_track(self, track: Track) -> None:
        if track.video_blob_id is None or track.video_blob_ref_freed:
            return
        track.video_blob_ref_freed = True
        await self._session.flush()
        res = await self._session.execute(
            select(VideoBlob).where(VideoBlob.id == track.video_blob_id)
        )
        blob = res.scalars().first()
        if blob is None:
            return
        track.video_blob_id = None
        new_ref = blob.ref_count - 1
        blob.ref_count = new_ref
        await self._session.flush()
        if new_ref <= 0:
            try:
                await s3.delete_object(blob.s3_key)
            except Exception as exc:
                logger.warning(
                    "video_blob_s3_delete_failed",
                    s3_key=blob.s3_key,
                    error=str(exc),
                )
            await self._session.delete(blob)
            await self._session.flush()
