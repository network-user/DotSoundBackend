from __future__ import annotations

import asyncio
import hashlib
import os

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audio_storage_metrics, s3
from app.models.audio_blob import AudioBlob
from app.models.track import Track

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_HASH_CHUNK = 1024 * 1024


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file_hex(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(_HASH_CHUNK):
            sha.update(chunk)
    return sha.hexdigest()


class AudioBlobService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_source_sha256(
        self, source_sha256: str
    ) -> AudioBlob | None:
        """Return the canonical blob for an already-known source, if any."""
        if not source_sha256:
            return None
        res = await self._session.execute(
            select(AudioBlob).where(AudioBlob.source_sha256 == source_sha256)
        )
        return res.scalars().first()

    async def claim_source(
        self,
        *,
        blob: AudioBlob,
        source_sha256: str,
    ) -> None:
        """Tag a freshly-built blob with the originating source hash.

        Idempotent: a concurrent transcode of the same source may have
        already filled the column, in which case we leave the existing
        value alone. A non-unique mismatch would be a programmer bug
        because the partial unique index guards against it.
        """
        if not source_sha256:
            return
        b = await self._session.get(AudioBlob, blob.id)
        if b is None:
            return
        if b.source_sha256 is None:
            b.source_sha256 = source_sha256
            await self._session.flush()

    async def set_hls_manifest_key(
        self,
        *,
        blob: AudioBlob,
        hls_manifest_key: str,
    ) -> None:
        """Record the shared HLS bundle key. First writer wins."""
        if not hls_manifest_key:
            return
        b = await self._session.get(AudioBlob, blob.id)
        if b is None:
            return
        if b.hls_manifest_key is None:
            b.hls_manifest_key = hls_manifest_key
            await self._session.flush()

    async def attach_pending_tracks(
        self,
        *,
        source_sha256: str,
        blob: AudioBlob,
    ) -> int:
        """Attach a freshly-built blob to every Track that claimed the same
        source while transcode was in flight. Returns the number of tracks
        reconciled (not counting the one that drove the transcode).
        """
        if not source_sha256:
            return 0
        res = await self._session.execute(
            select(Track).where(
                Track.source_sha256 == source_sha256,
                Track.blob_id.is_(None),
            )
        )
        pending = list(res.scalars().all())
        if not pending:
            return 0
        b = await self._session.get(AudioBlob, blob.id)
        if b is None:
            return 0
        for t in pending:
            b.ref_count = b.ref_count + 1
            t.file_key = b.s3_key
            t.blob_id = b.id
            t.blob_ref_freed = False
            t.processing_status = "active"
            if b.hls_manifest_key:
                t.hls_manifest_key = b.hls_manifest_key
        await self._session.flush()
        return len(pending)

    async def get_or_create_from_bytes(
        self,
        data: bytes,
        extension: str,
        content_type: str,
    ) -> tuple[AudioBlob, bool]:
        """Return (row, created).

        ``created`` is True for a new DB row; False on reuse.

        S3 is only written for a new logical content hash; a concurrent insert
        may have stored the same hash first, in which case the CAS put may be
        idempotent and we still return the existing row.
        """
        sha = _sha256_hex(data)
        res0 = await self._session.execute(
            select(AudioBlob).where(AudioBlob.content_sha256 == sha)
        )
        existing0 = res0.scalars().first()
        if existing0 is not None:
            audio_storage_metrics.log_blob_dedup_hit(
                size_bytes=len(data), content_sha256=sha
            )
            return existing0, False

        s3_key = await s3.put_cas_audio(data, sha, extension, content_type)
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
            audio_storage_metrics.log_s3_put_skipped(content_sha256=sha)
            r2 = await self._session.execute(
                select(AudioBlob).where(AudioBlob.content_sha256 == sha)
            )
            return r2.scalars().one(), False

        audio_storage_metrics.log_blob_dedup_miss(
            size_bytes=len(data), content_sha256=sha
        )
        return row, True

    async def get_or_create_from_file(
        self,
        file_path: str,
        extension: str,
        content_type: str,
    ) -> tuple[AudioBlob, bool]:
        """File-based twin of ``get_or_create_from_bytes``.

        Hashes and uploads straight from disk so audio-sized payloads
        (transcode outputs) never sit in RAM as one bytes object.
        Same dedup/race semantics as the bytes variant.
        """
        sha = await asyncio.to_thread(_sha256_file_hex, file_path)
        size = os.path.getsize(file_path)
        res0 = await self._session.execute(
            select(AudioBlob).where(AudioBlob.content_sha256 == sha)
        )
        existing0 = res0.scalars().first()
        if existing0 is not None:
            audio_storage_metrics.log_blob_dedup_hit(
                size_bytes=size, content_sha256=sha
            )
            return existing0, False

        s3_key = await s3.put_cas_audio_from_file(
            file_path, sha, extension, content_type
        )
        row = AudioBlob(
            content_sha256=sha,
            s3_key=s3_key,
            content_type=content_type,
            size_bytes=size,
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
                size_bytes=size, content_sha256=sha
            )
            audio_storage_metrics.log_s3_put_skipped(content_sha256=sha)
            r2 = await self._session.execute(
                select(AudioBlob).where(AudioBlob.content_sha256 == sha)
            )
            return r2.scalars().one(), False

        audio_storage_metrics.log_blob_dedup_miss(
            size_bytes=size, content_sha256=sha
        )
        return row, True

    async def attach_playback_blob(
        self,
        track: Track,
        blob: AudioBlob,
    ) -> None:
        if track.blob_id is not None and track.blob_id != blob.id:
            raise ValueError("track already linked to a different blob")
        if track.blob_id == blob.id and not track.blob_ref_freed:
            return
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
        if locked is None or locked.blob_id is None or locked.blob_ref_freed:
            return
        b_res = await self._session.execute(
            select(AudioBlob)
            .where(AudioBlob.id == locked.blob_id)
            .with_for_update()
        )
        blob = b_res.scalars().one_or_none()
        if blob is None:
            return

        sibling_ct = int(
            await self._session.scalar(
                select(func.count()).where(
                    Track.blob_id == blob.id,
                    Track.id != locked.id,
                    Track.blob_ref_freed.is_(False),
                )
            )
            or 0
        )

        locked.blob_ref_freed = True

        async def _purge_blob_row() -> None:
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

        if blob.ref_count < 1:
            if sibling_ct > 0:
                blob.ref_count = sibling_ct
                await self._session.flush()
                return
            await _purge_blob_row()
            return

        new_ref = blob.ref_count - 1
        blob.ref_count = new_ref
        await self._session.flush()
        if new_ref <= 0:
            if sibling_ct > 0:
                blob.ref_count = sibling_ct
                await self._session.flush()
                return
            await _purge_blob_row()
