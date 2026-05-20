from __future__ import annotations

import hashlib
import mimetypes
import uuid
from dataclasses import asdict, dataclass
from os.path import splitext
from typing import Literal

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.audio_blob import AudioBlob
from app.models.track import Track
from app.services import compute_queue_service as q
from app.services.compute_job_dispatcher import dispatch_compute_job
from app.services.transcoding import transcode_and_upload_local

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_TELEGRAM = "telegram"
_REPAIR_FEATURE_VERSION = "telegram-import-repair-v1"
_URGENT_REPAIR_FEATURE_VERSION = "telegram-import-urgent-repair-v1"
_URGENT_REPAIR_PRIORITY = 0


@dataclass(frozen=True, slots=True)
class TelegramImportBackfillCandidate:
    track_id: int
    title: str
    artist: str | None
    file_key: str
    hls_manifest_key: str | None
    source_sha256: str | None
    blob_content_sha256: str | None


@dataclass(frozen=True, slots=True)
class TelegramImportBackfillItem:
    track_id: int
    status: Literal["candidate", "enqueued", "failed"]
    title: str
    file_key: str
    tmp_key: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TelegramImportBackfillReport:
    dry_run: bool
    found: int
    enqueued: int
    failed: int
    items: list[TelegramImportBackfillItem]

    def to_dict(self) -> dict[str, object]:
        return {
            "dry_run": self.dry_run,
            "found": self.found,
            "enqueued": self.enqueued,
            "failed": self.failed,
            "items": [asdict(item) for item in self.items],
        }


def _ext_from_key(file_key: str) -> str:
    _base, ext = splitext(str(file_key or "").rstrip("/"))
    clean = (ext or "").lstrip(".").lower()
    if not clean or len(clean) > 10:
        return "bin"
    return clean


def _guess_content_type(file_key: str) -> str:
    guessed, _ = mimetypes.guess_type(f"x.{_ext_from_key(file_key)}")
    return guessed or "audio/mpeg"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_telegram_source() -> ColumnElement[bool]:
    source = func.lower(func.coalesce(Track.source, ""))
    source_platform = func.lower(func.coalesce(Track.source_platform, ""))
    imported_from = func.lower(func.coalesce(Track.imported_from, ""))
    return or_(
        source == _TELEGRAM,
        source_platform == _TELEGRAM,
        imported_from == _TELEGRAM,
    )


def _needs_playback_repair() -> ColumnElement[bool]:
    file_key = func.lower(func.coalesce(Track.file_key, ""))
    missing_hls = or_(
        Track.hls_manifest_key.is_(None),
        Track.hls_manifest_key == "",
    )
    not_mp3_progressive = ~file_key.like("%.mp3")
    return missing_hls | not_mp3_progressive


class TelegramImportBackfillService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_candidates(
        self,
        *,
        limit: int = 100,
    ) -> list[TelegramImportBackfillCandidate]:
        if limit <= 0:
            return []
        stmt = (
            select(
                Track.id,
                Track.title,
                Track.artist,
                Track.file_key,
                Track.hls_manifest_key,
                Track.source_sha256,
                AudioBlob.content_sha256,
            )
            .outerjoin(AudioBlob, Track.blob_id == AudioBlob.id)
            .where(
                Track.is_active.is_(True),
                Track.deleted_at.is_(None),
                Track.file_key.isnot(None),
                Track.file_key != "",
                Track.access_mode == "internal_stream",
                _is_telegram_source(),
                _needs_playback_repair(),
            )
            .order_by(Track.id.asc())
            .limit(limit)
        )
        rows = await self._session.execute(stmt)
        out: list[TelegramImportBackfillCandidate] = []
        for row in rows.all():
            out.append(
                TelegramImportBackfillCandidate(
                    track_id=int(row.id),
                    title=str(row.title or ""),
                    artist=row.artist,
                    file_key=str(row.file_key),
                    hls_manifest_key=row.hls_manifest_key,
                    source_sha256=row.source_sha256,
                    blob_content_sha256=row.content_sha256,
                )
            )
        return out

    async def run(
        self,
        *,
        limit: int = 100,
        dry_run: bool = True,
        urgent: bool = False,
    ) -> TelegramImportBackfillReport:
        candidates = await self.list_candidates(limit=limit)
        if dry_run:
            return TelegramImportBackfillReport(
                dry_run=True,
                found=len(candidates),
                enqueued=0,
                failed=0,
                items=[
                    TelegramImportBackfillItem(
                        track_id=c.track_id,
                        status="candidate",
                        title=c.title,
                        file_key=c.file_key,
                    )
                    for c in candidates
                ],
            )

        items: list[TelegramImportBackfillItem] = []
        enqueued = 0
        failed = 0
        for candidate in candidates:
            try:
                item = await self._enqueue_candidate(
                    candidate,
                    urgent=urgent,
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.warning(
                    "telegram_import_backfill_failed",
                    track_id=candidate.track_id,
                    error=str(exc),
                )
                items.append(
                    TelegramImportBackfillItem(
                        track_id=candidate.track_id,
                        status="failed",
                        title=candidate.title,
                        file_key=candidate.file_key,
                        error=str(exc),
                    )
                )
            else:
                enqueued += 1
                items.append(item)

        return TelegramImportBackfillReport(
            dry_run=False,
            found=len(candidates),
            enqueued=enqueued,
            failed=failed,
            items=items,
        )

    async def _enqueue_candidate(
        self,
        candidate: TelegramImportBackfillCandidate,
        *,
        urgent: bool = False,
    ) -> TelegramImportBackfillItem:
        raw = await s3.download_object(candidate.file_key)
        ext = _ext_from_key(candidate.file_key)
        content_type = _guess_content_type(candidate.file_key)
        source_sha256 = (
            candidate.source_sha256
            or candidate.blob_content_sha256
            or _sha256_hex(raw)
        )
        tmp_key = f"tmp-transcode/{uuid.uuid4().hex}.{ext}"
        await s3.upload_object(tmp_key, raw, content_type)
        if urgent:
            await repair_telegram_import_transcode_task.kiq(
                track_id=candidate.track_id,
                raw_key=tmp_key,
                original_filename=f"audio.{ext}",
                source_sha256=source_sha256,
                priority=_URGENT_REPAIR_PRIORITY,
                feature_version=_URGENT_REPAIR_FEATURE_VERSION,
            )
        else:
            await repair_telegram_import_transcode_task.kiq(
                track_id=candidate.track_id,
                raw_key=tmp_key,
                original_filename=f"audio.{ext}",
                source_sha256=source_sha256,
            )
        track = await self._session.get(Track, candidate.track_id)
        if track is not None and not track.source_sha256:
            track.source_sha256 = source_sha256
            await self._session.flush()
        from app.services.search_index_notify import schedule_reindex_track

        await schedule_reindex_track(candidate.track_id)
        logger.info(
            "telegram_import_backfill_enqueued",
            track_id=candidate.track_id,
            tmp_key=tmp_key,
        )
        return TelegramImportBackfillItem(
            track_id=candidate.track_id,
            status="enqueued",
            title=candidate.title,
            file_key=candidate.file_key,
            tmp_key=tmp_key,
        )


@broker.task
async def repair_telegram_import_transcode_task(
    track_id: int,
    raw_key: str,
    original_filename: str,
    source_sha256: str | None = None,
    priority: int | None = None,
    feature_version: str = _REPAIR_FEATURE_VERSION,
) -> None:
    async with AsyncSessionLocal() as session:
        await dispatch_compute_job(
            session,
            job_type=q.JOB_TRACK_TRANSCODING,
            target_kind=q.TARGET_KIND_TRACK,
            target_id=track_id,
            payload={
                "track_id": track_id,
                "raw_key": raw_key,
                "original_filename": original_filename,
                "source_sha256": source_sha256,
            },
            feature_version=feature_version,
            priority=priority,
            local_handler=transcode_and_upload_local,
        )
        await session.commit()
