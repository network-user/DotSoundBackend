"""On-demand and scheduled normalization for internal-stream UGC playback.

Ensures Telegram imports and manual uploads are transcoded to MP3 + HLS.
Scheduling is idempotent: Redis cooldown per track, compute-job dedupe, and
optional admin force-retry with a fresh feature_version.
"""

from __future__ import annotations

import hashlib
import mimetypes
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from os.path import splitext
from typing import Literal

import structlog
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.config import settings
from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.core.tkq import broker
from app.models.audio_blob import AudioBlob
from app.models.track import Track
from app.services import compute_queue_service as q
from app.services.compute_job_dispatcher import dispatch_compute_job
from app.services.transcoding import transcode_and_upload_local

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_TELEGRAM = "telegram"
_FEATURE_VERSION = "ugc-playback-normalize-v1"
_URGENT_FEATURE_VERSION = "ugc-playback-normalize-urgent-v1"
_URGENT_PRIORITY = 0
_COOLDOWN_KEY_PREFIX = "ugc_norm:cooldown:"
_UNRECOVERABLE_KEY_PREFIX = "ugc_norm:unrecoverable:"
_UNRECOVERABLE_TTL_SECONDS = 7 * 24 * 3600


def _force_retry_feature_version(base: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{base}-retry-{stamp}"


@dataclass(frozen=True, slots=True)
class UgcPlaybackNormalizeCandidate:
    track_id: int
    title: str
    artist: str | None
    file_key: str
    hls_manifest_key: str | None
    source_sha256: str | None
    blob_content_sha256: str | None


@dataclass(frozen=True, slots=True)
class UgcPlaybackNormalizeItem:
    track_id: int
    status: Literal[
        "candidate",
        "enqueued",
        "failed",
        "skipped",
        "unrecoverable",
    ]
    title: str
    file_key: str
    tmp_key: str | None = None
    error: str | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class UgcPlaybackNormalizeReport:
    dry_run: bool
    found: int
    enqueued: int
    failed: int
    skipped: int
    unrecoverable: int
    items: list[UgcPlaybackNormalizeItem]

    def to_dict(self) -> dict[str, object]:
        return {
            "dry_run": self.dry_run,
            "found": self.found,
            "enqueued": self.enqueued,
            "failed": self.failed,
            "skipped": self.skipped,
            "unrecoverable": self.unrecoverable,
            "items": [asdict(item) for item in self.items],
        }


@dataclass(frozen=True, slots=True)
class UgcPlaybackNormalizeScheduleResult:
    action: Literal[
        "disabled",
        "not_needed",
        "unrecoverable",
        "cooldown",
        "already_queued",
        "enqueued",
        "failed",
    ]
    detail: str = ""
    tmp_key: str | None = None


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


def _is_telegram_source_sql() -> ColumnElement[bool]:
    source = func.lower(func.coalesce(Track.source, ""))
    source_platform = func.lower(func.coalesce(Track.source_platform, ""))
    imported_from = func.lower(func.coalesce(Track.imported_from, ""))
    return or_(
        source == _TELEGRAM,
        source_platform == _TELEGRAM,
        imported_from == _TELEGRAM,
    )


def _is_internal_stream_ugc_sql() -> ColumnElement[bool]:
    access = func.lower(func.coalesce(Track.access_mode, ""))
    catalog = func.lower(func.coalesce(Track.catalog_type, ""))
    source = func.lower(func.coalesce(Track.source, ""))
    return and_(
        access == "internal_stream",
        catalog == "ugc",
        or_(
            _is_telegram_source_sql(),
            source == "internal",
        ),
    )


def _needs_playback_normalize_sql() -> ColumnElement[bool]:
    file_key = func.lower(func.coalesce(Track.file_key, ""))
    missing_hls = or_(
        Track.hls_manifest_key.is_(None),
        Track.hls_manifest_key == "",
    )
    not_mp3_progressive = ~file_key.like("%.mp3")
    stale_temp_key = or_(
        file_key.like("temp/%"),
        file_key.like("tmp-transcode/%"),
    )
    failed_processing = and_(
        Track.processing_status == "error",
        or_(missing_hls, not_mp3_progressive, stale_temp_key),
    )
    return (
        missing_hls
        | not_mp3_progressive
        | stale_temp_key
        | failed_processing
    )


def _is_internal_stream_ugc_track(track: Track) -> bool:
    if (track.access_mode or "").lower() != "internal_stream":
        return False
    if (track.catalog_type or "").lower() != "ugc":
        return False
    source = (track.source or "").lower()
    sp = (track.source_platform or "").lower()
    imp = (track.imported_from or "").lower()
    if source == "telegram" or sp == "telegram" or imp == "telegram":
        return True
    return source == "internal"


def track_needs_ugc_playback_normalize(track: Track) -> bool:
    if not track.is_active or track.deleted_at is not None:
        return False
    if not _is_internal_stream_ugc_track(track):
        return False
    file_key = (track.file_key or "").strip()
    if not file_key:
        return False
    fk = file_key.lower()
    missing_hls = not (track.hls_manifest_key or "").strip()
    not_mp3 = not fk.endswith(".mp3")
    stale_temp = fk.startswith("temp/") or fk.startswith("tmp-transcode/")
    failed_processing = (
        track.processing_status == "error"
        and (missing_hls or not_mp3 or stale_temp)
    )
    return missing_hls or not_mp3 or stale_temp or failed_processing


def _cooldown_key(track_id: int) -> str:
    return f"{_COOLDOWN_KEY_PREFIX}{track_id}"


def _unrecoverable_key(track_id: int) -> str:
    return f"{_UNRECOVERABLE_KEY_PREFIX}{track_id}"


async def _is_marked_unrecoverable(track_id: int) -> bool:
    try:
        redis = get_redis_client()
        return bool(await redis.exists(_unrecoverable_key(track_id)))
    except Exception:  # noqa: BLE001
        return False


async def _mark_unrecoverable(track_id: int, *, reason: str) -> None:
    try:
        redis = get_redis_client()
        await redis.setex(
            _unrecoverable_key(track_id),
            _UNRECOVERABLE_TTL_SECONDS,
            reason[:500],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "ugc_normalize_unrecoverable_mark_failed",
            track_id=track_id,
            error=str(exc),
        )


async def _acquire_schedule_cooldown(track_id: int) -> bool:
    ttl = max(60, int(settings.ugc_playback_normalize_cooldown_seconds))
    try:
        redis = get_redis_client()
        acquired = await redis.set(
            _cooldown_key(track_id),
            "1",
            nx=True,
            ex=ttl,
        )
        return bool(acquired)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "ugc_normalize_cooldown_redis_failed",
            track_id=track_id,
            error=str(exc),
        )
        return True


async def _source_object_exists(file_key: str) -> bool:
    try:
        return await s3.object_exists(file_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "ugc_normalize_source_exists_check_failed",
            file_key=file_key,
            error=str(exc),
        )
        return False


class UgcPlaybackNormalizeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_candidates(
        self,
        *,
        limit: int = 100,
        track_ids: list[int] | None = None,
    ) -> list[UgcPlaybackNormalizeCandidate]:
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
                _is_internal_stream_ugc_sql(),
                _needs_playback_normalize_sql(),
            )
            .order_by(Track.id.asc())
            .limit(limit)
        )
        if track_ids:
            stmt = stmt.where(Track.id.in_(track_ids))
        rows = await self._session.execute(stmt)
        out: list[UgcPlaybackNormalizeCandidate] = []
        for row in rows.all():
            if await _is_marked_unrecoverable(int(row.id)):
                continue
            out.append(
                UgcPlaybackNormalizeCandidate(
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

    async def list_unrecoverable_candidates(
        self,
        *,
        limit: int = 100,
    ) -> list[UgcPlaybackNormalizeItem]:
        if limit <= 0:
            return []
        stmt = (
            select(
                Track.id,
                Track.title,
                Track.file_key,
            )
            .where(
                Track.is_active.is_(True),
                Track.deleted_at.is_(None),
                Track.file_key.isnot(None),
                Track.file_key != "",
                _is_internal_stream_ugc_sql(),
                _needs_playback_normalize_sql(),
            )
            .order_by(Track.id.asc())
            .limit(limit * 5)
        )
        rows = await self._session.execute(stmt)
        out: list[UgcPlaybackNormalizeItem] = []
        for row in rows.all():
            if len(out) >= limit:
                break
            track_id = int(row.id)
            file_key = str(row.file_key)
            if await _is_marked_unrecoverable(track_id):
                out.append(
                    UgcPlaybackNormalizeItem(
                        track_id=track_id,
                        status="unrecoverable",
                        title=str(row.title or ""),
                        file_key=file_key,
                        detail="marked_unrecoverable",
                    )
                )
                continue
            if await _source_object_exists(file_key):
                continue
            await _mark_unrecoverable(
                track_id,
                reason="source_missing_in_storage",
            )
            out.append(
                UgcPlaybackNormalizeItem(
                    track_id=track_id,
                    status="unrecoverable",
                    title=str(row.title or ""),
                    file_key=file_key,
                    detail="source_missing_in_storage",
                )
            )
        return out

    async def try_schedule_for_track(
        self,
        track: Track,
        *,
        trigger: str = "playback",
        urgent: bool = False,
        bypass_cooldown: bool = False,
        feature_version_override: str | None = None,
    ) -> UgcPlaybackNormalizeScheduleResult:
        if not settings.ugc_playback_normalize_on_playback_enabled:
            return UgcPlaybackNormalizeScheduleResult(
                action="disabled",
                detail="ugc_playback_normalize_on_playback_enabled=false",
            )
        if not track_needs_ugc_playback_normalize(track):
            return UgcPlaybackNormalizeScheduleResult(
                action="not_needed",
                detail="track does not need normalization",
            )
        if await _is_marked_unrecoverable(track.id):
            return UgcPlaybackNormalizeScheduleResult(
                action="unrecoverable",
                detail="source previously marked missing",
            )
        file_key = str(track.file_key or "")
        if not await _source_object_exists(file_key):
            await _mark_unrecoverable(
                track.id,
                reason="source_missing_in_storage",
            )
            return UgcPlaybackNormalizeScheduleResult(
                action="unrecoverable",
                detail="audio object missing in storage",
            )
        if not bypass_cooldown and not await _acquire_schedule_cooldown(
            track.id
        ):
            return UgcPlaybackNormalizeScheduleResult(
                action="cooldown",
                detail="normalization recently scheduled",
            )
        base_fv = (
            _URGENT_FEATURE_VERSION if urgent else _FEATURE_VERSION
        )
        feature_version = feature_version_override or base_fv
        existing = await q.find_existing_job(
            self._session,
            job_type=q.JOB_TRACK_TRANSCODING,
            target_kind=q.TARGET_KIND_TRACK,
            target_id=track.id,
            feature_version=feature_version,
        )
        if existing is not None and existing.status in (
            q.STATUS_PENDING,
            q.STATUS_CLAIMED,
        ):
            return UgcPlaybackNormalizeScheduleResult(
                action="already_queued",
                detail=f"compute job {existing.id} {existing.status}",
            )
        if (
            existing is not None
            and existing.status in (q.STATUS_SUCCEEDED, q.STATUS_FAILED)
            and feature_version_override is None
        ):
            feature_version = _force_retry_feature_version(base_fv)
        candidate = UgcPlaybackNormalizeCandidate(
            track_id=track.id,
            title=str(track.title or ""),
            artist=track.artist,
            file_key=file_key,
            hls_manifest_key=track.hls_manifest_key,
            source_sha256=track.source_sha256,
            blob_content_sha256=None,
        )
        if track.blob_id is not None:
            blob = await self._session.get(AudioBlob, track.blob_id)
            if blob is not None:
                candidate = UgcPlaybackNormalizeCandidate(
                    track_id=candidate.track_id,
                    title=candidate.title,
                    artist=candidate.artist,
                    file_key=candidate.file_key,
                    hls_manifest_key=candidate.hls_manifest_key,
                    source_sha256=candidate.source_sha256,
                    blob_content_sha256=blob.content_sha256,
                )
        try:
            item = await self._enqueue_candidate(
                candidate,
                urgent=urgent,
                feature_version=feature_version,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ugc_normalize_schedule_failed",
                track_id=track.id,
                trigger=trigger,
                error=str(exc),
            )
            return UgcPlaybackNormalizeScheduleResult(
                action="failed",
                detail=str(exc),
            )
        logger.info(
            "ugc_normalize_scheduled",
            track_id=track.id,
            trigger=trigger,
            urgent=urgent,
            feature_version=feature_version,
        )
        return UgcPlaybackNormalizeScheduleResult(
            action="enqueued",
            detail=trigger,
            tmp_key=item.tmp_key,
        )

    async def run(
        self,
        *,
        limit: int = 100,
        dry_run: bool = True,
        urgent: bool = False,
        force_retry: bool = False,
        track_ids: list[int] | None = None,
    ) -> UgcPlaybackNormalizeReport:
        candidates = await self.list_candidates(
            limit=limit,
            track_ids=track_ids,
        )
        if dry_run:
            return UgcPlaybackNormalizeReport(
                dry_run=True,
                found=len(candidates),
                enqueued=0,
                failed=0,
                skipped=0,
                unrecoverable=0,
                items=[
                    UgcPlaybackNormalizeItem(
                        track_id=c.track_id,
                        status="candidate",
                        title=c.title,
                        file_key=c.file_key,
                    )
                    for c in candidates
                ],
            )

        retry_feature_version: str | None = None
        if force_retry:
            base = _URGENT_FEATURE_VERSION if urgent else _FEATURE_VERSION
            retry_feature_version = _force_retry_feature_version(base)

        items: list[UgcPlaybackNormalizeItem] = []
        enqueued = 0
        failed = 0
        skipped = 0
        unrecoverable = 0
        for candidate in candidates:
            track = await self._session.get(Track, candidate.track_id)
            if track is None:
                skipped += 1
                items.append(
                    UgcPlaybackNormalizeItem(
                        track_id=candidate.track_id,
                        status="skipped",
                        title=candidate.title,
                        file_key=candidate.file_key,
                        detail="track not found",
                    )
                )
                continue
            result = await self.try_schedule_for_track(
                track,
                trigger="batch",
                urgent=urgent,
                bypass_cooldown=force_retry,
                feature_version_override=retry_feature_version,
            )
            if result.action == "enqueued":
                enqueued += 1
                items.append(
                    UgcPlaybackNormalizeItem(
                        track_id=candidate.track_id,
                        status="enqueued",
                        title=candidate.title,
                        file_key=candidate.file_key,
                        tmp_key=result.tmp_key,
                        detail=result.detail,
                    )
                )
            elif result.action == "unrecoverable":
                unrecoverable += 1
                items.append(
                    UgcPlaybackNormalizeItem(
                        track_id=candidate.track_id,
                        status="unrecoverable",
                        title=candidate.title,
                        file_key=candidate.file_key,
                        detail=result.detail,
                    )
                )
            elif result.action in ("cooldown", "already_queued", "not_needed"):
                skipped += 1
                items.append(
                    UgcPlaybackNormalizeItem(
                        track_id=candidate.track_id,
                        status="skipped",
                        title=candidate.title,
                        file_key=candidate.file_key,
                        detail=result.detail,
                    )
                )
            else:
                failed += 1
                items.append(
                    UgcPlaybackNormalizeItem(
                        track_id=candidate.track_id,
                        status="failed",
                        title=candidate.title,
                        file_key=candidate.file_key,
                        error=result.detail,
                    )
                )

        return UgcPlaybackNormalizeReport(
            dry_run=False,
            found=len(candidates),
            enqueued=enqueued,
            failed=failed,
            skipped=skipped,
            unrecoverable=unrecoverable,
            items=items,
        )

    async def _enqueue_candidate(
        self,
        candidate: UgcPlaybackNormalizeCandidate,
        *,
        urgent: bool = False,
        feature_version: str,
    ) -> UgcPlaybackNormalizeItem:
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
        priority = _URGENT_PRIORITY if urgent else None
        await repair_ugc_playback_normalize_task.kiq(
            track_id=candidate.track_id,
            raw_key=tmp_key,
            original_filename=f"audio.{ext}",
            source_sha256=source_sha256,
            priority=priority,
            feature_version=feature_version,
        )
        track = await self._session.get(Track, candidate.track_id)
        if track is not None and not track.source_sha256:
            track.source_sha256 = source_sha256
            await self._session.flush()
        from app.services.search_index_notify import schedule_reindex_track

        await schedule_reindex_track(candidate.track_id)
        return UgcPlaybackNormalizeItem(
            track_id=candidate.track_id,
            status="enqueued",
            title=candidate.title,
            file_key=candidate.file_key,
            tmp_key=tmp_key,
        )


async def maybe_schedule_ugc_playback_normalize(
    session: AsyncSession,
    track: Track,
    *,
    trigger: str = "playback",
) -> None:
    """Best-effort hook from playback paths; never raises to the client."""
    if not _is_internal_stream_ugc_track(track):
        return
    try:
        svc = UgcPlaybackNormalizeService(session)
        await svc.try_schedule_for_track(
            track,
            trigger=trigger,
            urgent=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "ugc_normalize_playback_hook_failed",
            track_id=track.id,
            trigger=trigger,
            error=str(exc),
        )


@broker.task
async def repair_ugc_playback_normalize_task(
    track_id: int,
    raw_key: str,
    original_filename: str,
    source_sha256: str | None = None,
    priority: int | None = None,
    feature_version: str = _FEATURE_VERSION,
) -> None:
    async with AsyncSessionLocal() as session:
        result = await dispatch_compute_job(
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
        logger.info(
            "ugc_playback_normalize_dispatched",
            track_id=track_id,
            feature_version=feature_version,
            status=result.status,
            job_id=result.job_id,
        )


@broker.task
async def sweep_ugc_playback_normalize_task(
    limit: int | None = None,
) -> dict[str, object]:
    sweep_limit = int(
        limit or settings.ugc_playback_normalize_sweep_limit
    )
    async with AsyncSessionLocal() as session:
        report = await UgcPlaybackNormalizeService(session).run(
            limit=sweep_limit,
            dry_run=False,
            urgent=False,
            force_retry=False,
        )
        await session.commit()
    summary = report.to_dict()
    logger.info("ugc_playback_normalize_sweep_complete", **summary)
    return summary
