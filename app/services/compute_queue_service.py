"""Generic compute-job queue (persistent, retry-aware).

Public API:
    enqueue(...)             -> idempotent insert, returns ComputeJob
    claim_next(...)          -> atomically lease one job for a worker
    mark_succeeded(...)      -> terminal: status=succeeded, store result
    mark_failed(...)         -> retry-with-backoff or terminal=failed
    requeue_stale_claims(...)-> recover claimed jobs past lease deadline
    queue_depth(...)         -> count by job_type/status
    dead_letter_jobs(...)    -> jobs in terminal failed state

Algorithms (scoring, similarity, normalization) and feature_version
semantics are defined inside `dotsound_private_core`. This module
is pure transport: it does not know what a job does.
"""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compute_job import ComputeJob
from app.models.compute_worker import ComputeWorker
from app.services.worker_job_control import worker_claims_blocked

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

DEFAULT_LEASE_MINUTES = 15
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_FEATURE_VERSION = "v1"
BACKOFF_BASE_SECONDS = 30
BACKOFF_MAX_SECONDS = 60 * 60  # 1 hour cap

STATUS_PENDING = "pending"
STATUS_CLAIMED = "claimed"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
TERMINAL_STATUSES = {STATUS_SUCCEEDED, STATUS_FAILED}

JOB_TRACK_AUDIO_FEATURES = "track_audio_features"
JOB_ARTIST_FEATURES_UPDATE = "artist_features_update"
JOB_ARTIST_SIMILARITY_INDEX = "artist_similarity_index"
JOB_TRACK_SIMILARITY_INDEX = "track_similarity_index"
JOB_CATALOG_INGEST_NORMALIZE = "catalog_ingest_normalize"

TARGET_KIND_TRACK = "track"
TARGET_KIND_ARTIST = "artist"

KNOWN_JOB_TYPES: frozenset[str] = frozenset(
    {
        JOB_TRACK_AUDIO_FEATURES,
        JOB_ARTIST_FEATURES_UPDATE,
        JOB_ARTIST_SIMILARITY_INDEX,
        JOB_TRACK_SIMILARITY_INDEX,
        JOB_CATALOG_INGEST_NORMALIZE,
    }
)


def _now() -> datetime:
    return datetime.now(UTC)


def _new_job_id() -> str:
    return f"cj_{secrets.token_hex(12)}"


def _supports_skip_locked(session: AsyncSession) -> bool:
    bind = session.get_bind()
    return getattr(bind.dialect, "name", "") == "postgresql"


def _backoff_for(attempts: int) -> int:
    """Exponential backoff: 30s, 60s, 120s, 240s, ... capped."""
    seconds = BACKOFF_BASE_SECONDS * (2 ** max(0, attempts - 1))
    return int(min(seconds, BACKOFF_MAX_SECONDS))


async def enqueue(
    session: AsyncSession,
    *,
    job_type: str,
    target_kind: str | None = None,
    target_id: str | int | None = None,
    payload: dict | None = None,
    feature_version: str = DEFAULT_FEATURE_VERSION,
    priority: int = 0,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    delay_seconds: int = 0,
) -> ComputeJob:
    """Insert or fetch a job. Idempotent on the unique key
    ``(job_type, target_kind, target_id, feature_version)``.

    Returns the existing row unchanged if one is present (regardless
    of its current status), so callers can post the same intent
    repeatedly without polluting the queue.
    """
    target_id_str = (
        None if target_id is None else str(target_id)
    )

    existing = await find_existing_job(
        session,
        job_type=job_type,
        target_kind=target_kind,
        target_id=target_id_str,
        feature_version=feature_version,
    )
    if existing is not None:
        return existing

    now = _now()
    next_at = (
        now + timedelta(seconds=delay_seconds)
        if delay_seconds > 0
        else now
    )
    job = ComputeJob(
        id=_new_job_id(),
        job_type=job_type,
        target_kind=target_kind,
        target_id=target_id_str,
        payload=payload,
        feature_version=feature_version,
        status=STATUS_PENDING,
        priority=int(priority),
        attempts=0,
        max_attempts=max(1, int(max_attempts)),
        next_attempt_at=next_at,
    )
    session.add(job)
    try:
        await session.flush()
    except IntegrityError:
        # Race: another caller inserted the same key between the
        # SELECT above and our INSERT. Roll back the failed insert
        # and return the now-visible row.
        await session.rollback()
        existing = await find_existing_job(
            session,
            job_type=job_type,
            target_kind=target_kind,
            target_id=target_id_str,
            feature_version=feature_version,
        )
        if existing is None:
            raise
        return existing
    return job


async def find_existing_job(
    session: AsyncSession,
    *,
    job_type: str,
    target_kind: str | None,
    target_id: str | int | None,
    feature_version: str = DEFAULT_FEATURE_VERSION,
) -> ComputeJob | None:
    """Look up a queued job by its idempotency key.

    Returns the row regardless of status (pending, claimed, succeeded,
    failed). Useful for callers that want to differentiate "newly
    enqueued" vs "already known" without inserting first.
    """
    if target_id is not None and not isinstance(target_id, str):
        target_id = str(target_id)
    stmt = select(ComputeJob).where(
        ComputeJob.job_type == job_type,
        ComputeJob.feature_version == feature_version,
    )
    if target_kind is None:
        stmt = stmt.where(ComputeJob.target_kind.is_(None))
    else:
        stmt = stmt.where(ComputeJob.target_kind == target_kind)
    if target_id is None:
        stmt = stmt.where(ComputeJob.target_id.is_(None))
    else:
        stmt = stmt.where(ComputeJob.target_id == target_id)
    return (
        await session.execute(stmt)
    ).scalar_one_or_none()


async def claim_next(
    session: AsyncSession,
    *,
    worker_id: str,
    job_types: Sequence[str],
    lease_minutes: int = DEFAULT_LEASE_MINUTES,
) -> ComputeJob | None:
    """Atomically lease the highest-priority pending job whose
    ``next_attempt_at`` has elapsed and whose ``job_type`` the worker
    can handle.

    Returns ``None`` if no job is eligible. The caller must commit
    the session for the lease to become visible to other workers.
    """
    if not job_types:
        return None
    now = _now()
    cw = (
        await session.execute(
            select(ComputeWorker).where(
                ComputeWorker.id == worker_id,
            ),
        )
    ).scalar_one_or_none()
    if cw is None or cw.revoked_at is not None:
        return None
    if worker_claims_blocked(cw, now=now):
        return None

    select_stmt = (
        select(ComputeJob.id)
        .where(
            ComputeJob.status == STATUS_PENDING,
            ComputeJob.job_type.in_(list(job_types)),
            ComputeJob.next_attempt_at <= now,
            or_(
                ComputeJob.pinned_worker_id.is_(None),
                ComputeJob.pinned_worker_id == worker_id,
            ),
        )
        .order_by(
            ComputeJob.priority.desc(),
            ComputeJob.next_attempt_at.asc(),
            ComputeJob.created_at.asc(),
        )
        .limit(1)
    )
    if _supports_skip_locked(session):
        select_stmt = select_stmt.with_for_update(
            skip_locked=True
        )
    job_id = (
        await session.execute(select_stmt)
    ).scalar_one_or_none()
    if not job_id:
        return None

    deadline = now + timedelta(minutes=int(lease_minutes))
    update_stmt = (
        update(ComputeJob)
        .where(
            ComputeJob.id == job_id,
            ComputeJob.status == STATUS_PENDING,
        )
        .values(
            status=STATUS_CLAIMED,
            pinned_worker_id=None,
            claimed_by=worker_id,
            claimed_at=now,
            claim_deadline_at=deadline,
            started_at=now,
            attempts=ComputeJob.attempts + 1,
        )
        .returning(ComputeJob)
        .execution_options(synchronize_session="fetch")
    )
    res = await session.execute(update_stmt)
    job = res.scalars().first()
    if job is None:
        return None
    logger.info(
        "compute_job_claimed",
        job_id=job.id,
        job_type=job.job_type,
        worker_id=worker_id,
        attempts=job.attempts,
    )
    return job


async def mark_succeeded(
    session: AsyncSession,
    *,
    job: ComputeJob,
    result: dict | None = None,
) -> None:
    job.status = STATUS_SUCCEEDED
    job.result = result
    job.finished_at = _now()
    job.last_error = None
    job.claim_deadline_at = None
    await session.flush()
    logger.info(
        "compute_job_succeeded",
        job_id=job.id,
        job_type=job.job_type,
        attempts=job.attempts,
    )


async def mark_failed(
    session: AsyncSession,
    *,
    job: ComputeJob,
    reason: str,
) -> None:
    """Increment attempts; if exhausted -> terminal failed; otherwise
    requeue with exponential backoff."""
    err = (reason or "")[:1024]
    if job.attempts >= job.max_attempts:
        job.status = STATUS_FAILED
        job.finished_at = _now()
        job.last_error = err
        job.claim_deadline_at = None
        await session.flush()
        logger.warning(
            "compute_job_dead_lettered",
            job_id=job.id,
            job_type=job.job_type,
            attempts=job.attempts,
            reason=err,
        )
        return
    backoff = _backoff_for(job.attempts)
    job.status = STATUS_PENDING
    job.next_attempt_at = _now() + timedelta(seconds=backoff)
    job.last_error = err
    job.claimed_by = None
    job.claimed_at = None
    job.claim_deadline_at = None
    job.started_at = None
    await session.flush()
    logger.info(
        "compute_job_retrying",
        job_id=job.id,
        job_type=job.job_type,
        attempts=job.attempts,
        backoff_seconds=backoff,
        reason=err,
    )


async def requeue_stale_claims(
    session: AsyncSession,
    *,
    grace_seconds: int = 0,
    limit: int = 100,
) -> int:
    """Move jobs whose lease deadline has passed back to pending.

    Returns count of recovered jobs. Idempotent and safe to call on
    a schedule (e.g. every minute by a background task).
    """
    cutoff = _now() - timedelta(seconds=int(grace_seconds))
    select_stmt = (
        select(ComputeJob.id)
        .where(
            ComputeJob.status == STATUS_CLAIMED,
            ComputeJob.claim_deadline_at.is_not(None),
            ComputeJob.claim_deadline_at < cutoff,
        )
        .limit(int(limit))
    )
    ids = [
        row
        for row in (
            await session.execute(select_stmt)
        ).scalars()
    ]
    if not ids:
        return 0
    update_stmt = (
        update(ComputeJob)
        .where(ComputeJob.id.in_(ids))
        .values(
            status=STATUS_PENDING,
            claimed_by=None,
            claimed_at=None,
            claim_deadline_at=None,
            started_at=None,
        )
        .execution_options(synchronize_session="fetch")
    )
    res = await session.execute(update_stmt)
    rowcount = int(res.rowcount or len(ids))
    logger.info(
        "compute_jobs_requeued_stale",
        count=rowcount,
    )
    return rowcount


async def queue_depth(
    session: AsyncSession,
    *,
    job_type: str | None = None,
) -> dict[str, int]:
    """Return ``{status: count}`` for the queue, optionally filtered."""
    stmt = select(
        ComputeJob.status,
        func.count(ComputeJob.id),
    )
    if job_type is not None:
        stmt = stmt.where(ComputeJob.job_type == job_type)
    stmt = stmt.group_by(ComputeJob.status)
    rows = (await session.execute(stmt)).all()
    return {str(status): int(count) for status, count in rows}


async def dead_letter_jobs(
    session: AsyncSession,
    *,
    limit: int = 100,
    job_type: str | None = None,
) -> list[ComputeJob]:
    stmt = (
        select(ComputeJob)
        .where(ComputeJob.status == STATUS_FAILED)
        .order_by(ComputeJob.finished_at.desc())
        .limit(int(limit))
    )
    if job_type is not None:
        stmt = stmt.where(ComputeJob.job_type == job_type)
    return [row for row in (await session.execute(stmt)).scalars()]


async def oldest_pending_age_seconds(
    session: AsyncSession,
    *,
    job_type: str | None = None,
) -> float | None:
    """Age (in seconds) of the oldest pending job.

    Used to surface 'queue is backing up' in `/internal/compute/status`.
    Returns None if the queue has no pending work.
    """
    stmt = select(func.min(ComputeJob.next_attempt_at)).where(
        ComputeJob.status == STATUS_PENDING,
    )
    if job_type is not None:
        stmt = stmt.where(ComputeJob.job_type == job_type)
    oldest = (await session.execute(stmt)).scalar_one_or_none()
    if oldest is None:
        return None
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=UTC)
    return max(0.0, (_now() - oldest).total_seconds())


async def enqueue_track_audio_features(
    session: AsyncSession,
    *,
    track_id: int,
    feature_version: str = DEFAULT_FEATURE_VERSION,
    priority: int = 0,
    payload: dict | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> ComputeJob:
    return await enqueue(
        session,
        job_type=JOB_TRACK_AUDIO_FEATURES,
        target_kind=TARGET_KIND_TRACK,
        target_id=track_id,
        feature_version=feature_version,
        priority=priority,
        payload=payload,
        max_attempts=max_attempts,
    )


async def enqueue_artist_features(
    session: AsyncSession,
    *,
    artist_id: int,
    feature_version: str = DEFAULT_FEATURE_VERSION,
    priority: int = 0,
    payload: dict | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> ComputeJob:
    return await enqueue(
        session,
        job_type=JOB_ARTIST_FEATURES_UPDATE,
        target_kind=TARGET_KIND_ARTIST,
        target_id=artist_id,
        feature_version=feature_version,
        priority=priority,
        payload=payload,
        max_attempts=max_attempts,
    )


async def enqueue_artist_similarity_index(
    session: AsyncSession,
    *,
    artist_id: int,
    feature_version: str = DEFAULT_FEATURE_VERSION,
    priority: int = 0,
    payload: dict | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> ComputeJob:
    return await enqueue(
        session,
        job_type=JOB_ARTIST_SIMILARITY_INDEX,
        target_kind=TARGET_KIND_ARTIST,
        target_id=artist_id,
        feature_version=feature_version,
        priority=priority,
        payload=payload,
        max_attempts=max_attempts,
    )


async def enqueue_track_similarity_index(
    session: AsyncSession,
    *,
    track_id: int,
    feature_version: str = DEFAULT_FEATURE_VERSION,
    priority: int = 0,
    payload: dict | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> ComputeJob:
    return await enqueue(
        session,
        job_type=JOB_TRACK_SIMILARITY_INDEX,
        target_kind=TARGET_KIND_TRACK,
        target_id=track_id,
        feature_version=feature_version,
        priority=priority,
        payload=payload,
        max_attempts=max_attempts,
    )


async def enqueue_catalog_ingest_normalize(
    session: AsyncSession,
    *,
    track_id: int,
    feature_version: str = DEFAULT_FEATURE_VERSION,
    priority: int = 0,
    payload: dict | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> ComputeJob:
    return await enqueue(
        session,
        job_type=JOB_CATALOG_INGEST_NORMALIZE,
        target_kind=TARGET_KIND_TRACK,
        target_id=track_id,
        feature_version=feature_version,
        priority=priority,
        payload=payload,
        max_attempts=max_attempts,
    )


async def queue_health_snapshot(
    session: AsyncSession,
) -> dict[str, Any]:
    by_type: dict[str, dict[str, int]] = {}
    oldest: dict[str, float] = {}
    for jt in sorted(KNOWN_JOB_TYPES):
        by_type[jt] = await queue_depth(
            session,
            job_type=jt,
        )
        age = await oldest_pending_age_seconds(
            session,
            job_type=jt,
        )
        if age is not None:
            oldest[jt] = age
    return {
        "by_type": by_type,
        "oldest_pending_sec": oldest,
    }


__all__ = [
    "DEFAULT_FEATURE_VERSION",
    "DEFAULT_LEASE_MINUTES",
    "DEFAULT_MAX_ATTEMPTS",
    "STATUS_CLAIMED",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_SUCCEEDED",
    "TERMINAL_STATUSES",
    "JOB_ARTIST_FEATURES_UPDATE",
    "JOB_ARTIST_SIMILARITY_INDEX",
    "JOB_CATALOG_INGEST_NORMALIZE",
    "JOB_TRACK_AUDIO_FEATURES",
    "JOB_TRACK_SIMILARITY_INDEX",
    "KNOWN_JOB_TYPES",
    "TARGET_KIND_ARTIST",
    "TARGET_KIND_TRACK",
    "claim_next",
    "dead_letter_jobs",
    "enqueue",
    "enqueue_artist_features",
    "enqueue_artist_similarity_index",
    "enqueue_catalog_ingest_normalize",
    "enqueue_track_audio_features",
    "enqueue_track_similarity_index",
    "find_existing_job",
    "mark_failed",
    "mark_succeeded",
    "oldest_pending_age_seconds",
    "queue_depth",
    "queue_health_snapshot",
    "requeue_stale_claims",
]
