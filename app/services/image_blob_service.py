from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.models.image_blob import ImageBlob
from app.models.track import Track

if TYPE_CHECKING:
    from app.models.user import User

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ImageBlobService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_from_bytes(
        self,
        data: bytes,
        extension: str,
        content_type: str,
    ) -> tuple[ImageBlob, bool]:
        """Return (row, created). `created` is True for a new DB row; False on reuse."""
        sha = _sha256_hex(data)
        res = await self._session.execute(
            select(ImageBlob).where(ImageBlob.content_sha256 == sha)
        )
        existing = res.scalars().first()
        if existing is not None:
            logger.debug("image_blob_dedup_hit", content_sha256=sha)
            return existing, False

        s3_key = await s3.put_cas_image(data, sha, extension, content_type)
        row = ImageBlob(
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
                "image_blob_dedup_hit_race", content_sha256=sha
            )
            r2 = await self._session.execute(
                select(ImageBlob).where(ImageBlob.content_sha256 == sha)
            )
            return r2.scalars().one(), False

        logger.debug("image_blob_created", content_sha256=sha)
        return row, True

    async def attach(
        self,
        blob: ImageBlob,
    ) -> None:
        b = await self._session.get(ImageBlob, blob.id)
        if b is None:
            return
        b.ref_count = b.ref_count + 1
        await self._session.flush()

    async def try_release_for_track(self, track: Track) -> None:
        if track.cover_blob_id is None or track.cover_blob_ref_freed:
            return
        track.cover_blob_ref_freed = True
        await self._session.flush()
        await self.try_release(track.cover_blob_id)

    async def try_release_for_user(self, user: User) -> None:
        if user.avatar_blob_id is None or user.avatar_blob_ref_freed:
            return
        user.avatar_blob_ref_freed = True
        await self._session.flush()
        await self.try_release(user.avatar_blob_id)

    async def try_release(self, blob_id: int) -> None:
        res = await self._session.execute(
            select(ImageBlob).where(ImageBlob.id == blob_id)
        )
        blob = res.scalars().first()
        if blob is None:
            return
        new_ref = blob.ref_count - 1
        blob.ref_count = new_ref
        await self._session.flush()
        if new_ref <= 0:
            try:
                await s3.delete_object(blob.s3_key)
            except Exception as exc:
                logger.warning(
                    "image_blob_s3_delete_failed",
                    s3_key=blob.s3_key,
                    error=str(exc),
                )
            await self._session.delete(blob)
            await self._session.flush()
