from __future__ import annotations

import hashlib

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audio_storage_metrics, s3
from app.models.audio_blob import AudioBlob
from app.models.track import Track

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class AudioBlobService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_from_bytes(
        self,
        data: bytes,
        extension: str,
        content_type: str,
    ) -> tuple[AudioBlob, bool]:
        """Return (row, created). `created` is True for a new DB row; False on reuse.

        S3 is only written for a new logical content hash; a concurrent insert
        may have stored the same hash first, in which case the CAS put may be
        idempotent and we still return the existing row.
        """
        sha = _sha256_hex(data)
        res0 = await self._session.execute(
            select(AudioBlob).where(
                AudioBlob.content_sha256 == sha
            )
        )
        existing0 = res0.scalars().first()
        if existing0 is not None:
            audio_storage_metrics.log_blob_dedup_hit(
                size_bytes=len(data), content_sha256=sha
            )
            return existing0, False

        s3_key = await s3.put_cas_audio(
            data, sha, extension, content_type
        )
        row = AudioBlob(
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
            audio_storage_metrics.log_blob_dedup_hit(
                size_bytes=len(data), content_sha256=sha
            )
            audio_storage_metrics.log_s3_put_skipped(
                content_sha256=sha
            )
            r2 = await self._session.execute(
                select(AudioBlob).where(
                    AudioBlob.content_sha256 == sha
                )
            )
            return r2.scalars().one(), False

        audio_storage_metrics.log_blob_dedup_miss(
            size_bytes=len(data), content_sha256=sha
        )
        return row, True

    async def attach_playback_blob(
        self,
        track: Track,
        blob: AudioBlob,
    ) -> None:
        if track.blob_id is not None and track.blob_id != blob.id:
            raise ValueError("track already linked to a different blob")
        b = await self._session.get(AudioBlob, blob.id)
        if b is None:
            return
        b.ref_count = b.ref_count + 1
        track.file_key = b.s3_key
        track.blob_id = b.id
        track.blob_ref_freed = False
        await self._session.flush()

    async def try_release_for_track(
        self,
        track: Track,
    ) -> None:
        if track.blob_id is None or track.blob_ref_freed:
            return
        t_res = await self._session.execute(
            select(Track).where(Track.id == track.id)
        )
        locked = t_res.scalars().first()
        if (
            locked is None
            or locked.blob_id is None
            or locked.blob_ref_freed
        ):
            return
        b_res = await self._session.execute(
            select(AudioBlob).where(
                AudioBlob.id == locked.blob_id
            )
        )
        blob = b_res.scalars().one_or_none()
        if blob is None:
            return

        locked.blob_ref_freed = True
        if blob.ref_count < 1:
            try:
                await s3.delete_object(blob.s3_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "audio_blob_s3_delete_failed",
                    s3_key=blob.s3_key,
                    error=str(exc),
                )
            await self._session.delete(blob)
            await self._session.flush()
            return
        new_ref = blob.ref_count - 1
        blob.ref_count = new_ref
        await self._session.flush()
        if new_ref <= 0:
            try:
                await s3.delete_object(blob.s3_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "audio_blob_s3_delete_failed",
                    s3_key=blob.s3_key,
                    error=str(exc),
                )
            await self._session.delete(blob)
            await self._session.flush()
