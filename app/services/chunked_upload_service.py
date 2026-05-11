"""Chunked upload orchestration for resumable, cancellable v2 uploads.

The flow uses S3 multipart-upload as the storage primitive so that
each PUT lands directly in the bucket and the final assembly is a
single ``complete_multipart_upload`` call. A row in
``upload_sessions`` mirrors the multipart state and lets the client
resume after reload/network loss.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import s3
from app.models.upload_session import UploadSession
from app.services.upload_service import (
    _ALLOWED_AUDIO_MIMES,
    _MAX_AUDIO_BYTES,
    _MAX_STORAGE_QUOTA,
    UploadService,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

try:
    from dotsound_private_core.services.upload_policy import (
        UPLOAD_CHUNK_BYTES,
        UPLOAD_SESSION_TTL_SECONDS,
        expected_chunks_for,
    )
except ImportError:  # pragma: no cover - fallback for early bootstraps
    UPLOAD_CHUNK_BYTES = 8 * 1024 * 1024
    UPLOAD_SESSION_TTL_SECONDS = 24 * 60 * 60

    def expected_chunks_for(total_size: int) -> int:
        if total_size <= 0:
            return 0
        return (total_size + UPLOAD_CHUNK_BYTES - 1) // UPLOAD_CHUNK_BYTES


def _safe_filename(name: str) -> str:
    return re.sub(r"[^\w.\-]", "_", name or "track")[:100]


class ChunkedUploadService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def init(
        self,
        *,
        user_id: int,
        filename: str,
        mime: str,
        total_size: int,
        audio_hash: str | None,
        meta: dict,
    ) -> UploadSession:
        if mime not in _ALLOWED_AUDIO_MIMES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported audio format: {mime}",
            )
        if total_size > _MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Audio file exceeds 100 MB limit",
            )
        if total_size <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="total_size must be > 0",
            )

        from app.repositories.track import TrackRepository

        used = await TrackRepository(self._session).get_total_uploaded_bytes(
            user_id
        )
        if used + total_size > _MAX_STORAGE_QUOTA:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quota Exceeded: 3GB maximum storage reached.",
            )

        upload_id = str(uuid.uuid4())
        safe = _safe_filename(filename)
        s3_key = f"temp/uploads/{user_id}/{upload_id}/{safe}"

        async with s3.get_s3_client() as client:
            resp = await client.create_multipart_upload(
                Bucket=settings.minio_bucket,
                Key=s3_key,
                ContentType=mime,
            )
            multipart_id = resp["UploadId"]

        expected = expected_chunks_for(total_size)
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=UPLOAD_SESSION_TTL_SECONDS)

        record = UploadSession(
            upload_id=upload_id,
            user_id=user_id,
            filename=filename[:512],
            mime=mime,
            total_size=total_size,
            audio_hash=audio_hash,
            chunk_size=UPLOAD_CHUNK_BYTES,
            expected_chunks=expected,
            completed_chunks=[],
            s3_key=s3_key,
            s3_multipart_id=multipart_id,
            s3_parts=[],
            status="active",
            meta=meta,
            expires_at=expires_at,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        logger.info(
            "upload_chunked_init",
            upload_id=upload_id,
            total_size=total_size,
            expected_chunks=expected,
        )
        return record

    async def upload_chunk(
        self,
        *,
        upload_id: str,
        user_id: int,
        chunk_index: int,
        data: bytes,
    ) -> UploadSession:
        record = await self._load_active(upload_id, user_id)

        if chunk_index < 0 or chunk_index >= record.expected_chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="chunk_index out of range",
            )

        # idempotent: a re-uploaded chunk just overwrites the previous part
        is_last = chunk_index == record.expected_chunks - 1
        expected_chunk_size = (
            record.total_size - chunk_index * record.chunk_size
            if is_last
            else record.chunk_size
        )
        if len(data) != expected_chunk_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"chunk size mismatch: expected "
                    f"{expected_chunk_size}, got {len(data)}"
                ),
            )

        part_number = chunk_index + 1
        async with s3.get_s3_client() as client:
            put = await client.upload_part(
                Bucket=settings.minio_bucket,
                Key=record.s3_key,
                UploadId=record.s3_multipart_id,
                PartNumber=part_number,
                Body=data,
            )
            etag = put["ETag"]

        parts = list(record.s3_parts or [])
        parts = [p for p in parts if p.get("part_number") != part_number]
        parts.append({"part_number": part_number, "etag": etag})
        completed = sorted(
            set(list(record.completed_chunks or []) + [chunk_index])
        )

        await self._session.execute(
            update(UploadSession)
            .where(UploadSession.id == record.id)
            .values(
                s3_parts=parts,
                completed_chunks=completed,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def status(
        self, *, upload_id: str, user_id: int
    ) -> UploadSession:
        record = await self._load(upload_id, user_id)
        return record

    async def cancel(self, *, upload_id: str, user_id: int) -> None:
        record = await self._load(upload_id, user_id)
        if record.status != "active":
            return
        await self._abort_multipart(record)
        await self._session.execute(
            update(UploadSession)
            .where(UploadSession.id == record.id)
            .values(status="cancelled", updated_at=datetime.now(UTC))
        )
        await self._session.flush()

    async def complete(
        self,
        *,
        upload_id: str,
        user_id: int,
        cover_key: str | None = None,
    ):
        record = await self._load_active(upload_id, user_id)

        if len(record.completed_chunks or []) != record.expected_chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"incomplete upload: "
                    f"{len(record.completed_chunks or [])}/"
                    f"{record.expected_chunks} chunks"
                ),
            )

        parts_sorted = sorted(
            list(record.s3_parts or []),
            key=lambda p: p["part_number"],
        )
        async with s3.get_s3_client() as client:
            await client.complete_multipart_upload(
                Bucket=settings.minio_bucket,
                Key=record.s3_key,
                UploadId=record.s3_multipart_id,
                MultipartUpload={
                    "Parts": [
                        {
                            "PartNumber": p["part_number"],
                            "ETag": p["etag"],
                        }
                        for p in parts_sorted
                    ]
                },
            )

        try:
            source_sha256 = await s3.compute_sha256_streaming(
                record.s3_key
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "upload_chunked_source_hash_failed",
                upload_id=upload_id,
                error=str(exc),
            )
            source_sha256 = None

        if source_sha256:
            await self._session.execute(
                update(UploadSession)
                .where(UploadSession.id == record.id)
                .values(
                    source_sha256=source_sha256,
                    updated_at=datetime.now(UTC),
                )
            )
            await self._session.flush()

        meta = record.meta or {}
        upload_svc = UploadService(self._session)
        track = await upload_svc.finalize_from_s3(
            raw_key=record.s3_key,
            original_filename=record.filename,
            mime=record.mime,
            total_size=record.total_size,
            title=meta.get("title", record.filename),
            artist=meta.get("artist"),
            use_profile_artist=bool(meta.get("use_profile_artist", False)),
            genre=meta.get("genre"),
            cover_key=cover_key,
            uploader_id=record.user_id,
            is_public=bool(meta.get("is_public", True)),
            audio_hash=record.audio_hash,
            source_sha256=source_sha256,
            link_artists=True,
        )

        await self._session.execute(
            update(UploadSession)
            .where(UploadSession.id == record.id)
            .values(
                status="completed",
                track_id=track.id,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.flush()
        logger.info(
            "upload_chunked_complete",
            upload_id=upload_id,
            track_id=track.id,
        )
        return track

    async def _load(self, upload_id: str, user_id: int) -> UploadSession:
        result = await self._session.execute(
            select(UploadSession).where(
                UploadSession.upload_id == upload_id,
                UploadSession.user_id == user_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="upload session not found",
            )
        return record

    async def _load_active(
        self, upload_id: str, user_id: int
    ) -> UploadSession:
        record = await self._load(upload_id, user_id)
        if record.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"upload session is {record.status}",
            )
        if record.expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="upload session expired",
            )
        return record

    async def _abort_multipart(self, record: UploadSession) -> None:
        if not record.s3_multipart_id:
            return
        try:
            async with s3.get_s3_client() as client:
                await client.abort_multipart_upload(
                    Bucket=settings.minio_bucket,
                    Key=record.s3_key,
                    UploadId=record.s3_multipart_id,
                )
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "upload_chunked_abort_failed",
                upload_id=record.upload_id,
                error=str(exc),
            )
