"""Audio-compute worker lifecycle.

Worker registration, HMAC-signed request verification, heartbeat,
job claim/result/fail, OTT for audio download, and audit logging.
Pure transport: decisions like "is this CIDR allowed" come from
PrivateCore (`network_policy`).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import UTC, datetime, timedelta

import structlog
from dotsound_private_core.services.network_policy import (
    is_ip_in_cidrs,
)
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import get_redis_client
from app.models.compute_worker import ComputeWorker
from app.models.lyrics_job import LyricsJob
from app.services.worker_job_control import (
    worker_claims_blocked,
)
from app.models.worker_audit import WorkerAuditLog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

NONCE_KEY_PREFIX = "worker:nonce:"
OTT_KEY_PREFIX = "worker:ott:"
SUSPEND_FLAG_PREFIX = "worker:rl_strikes:"
_NONCE_TTL = 300
_OTT_TTL = 300
_TIMESTAMP_SKEW = 60
_DEFAULT_LEASE_MINUTES = 10
SIGNATURE_VERSION = "1"


class WorkerAuthError(Exception):
    pass


class WorkerNotFoundError(Exception):
    pass


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _supports_skip_locked(session: AsyncSession) -> bool:
    """True if the bound dialect supports FOR UPDATE SKIP LOCKED.

    PostgreSQL gets atomic, fair claim ordering. SQLite (used in
    tests) silently falls back to plain SELECT — this is fine
    because the test suite is single-threaded.
    """
    bind = session.get_bind()
    return getattr(
        bind.dialect, "name", ""
    ) == "postgresql"


def _signature_payload(
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body_sha: str,
) -> bytes:
    return (
        f"{method.upper()}\n{path}\n{timestamp}\n{nonce}\n"
        f"{body_sha}"
    ).encode()


def _compute_signature(
    secret: str,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    body_sha = hashlib.sha256(body or b"").hexdigest()
    payload = _signature_payload(
        method, path, timestamp, nonce, body_sha
    )
    return hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()


async def _check_nonce(worker_id: str, nonce: str) -> bool:
    redis = get_redis_client()
    key = f"{NONCE_KEY_PREFIX}{worker_id}:{nonce}"
    added = await redis.set(
        key, "1", ex=_NONCE_TTL, nx=True
    )
    return bool(added)


async def invalidate_worker_nonces(worker_id: str) -> int:
    """Drop all cached nonces for a worker (revoke / rotate).

    Cleans `worker:nonce:{worker_id}:*` so any signed request
    using a valid-but-cached nonce is forced to re-register a
    fresh one.
    """
    redis = get_redis_client()
    pattern = f"{NONCE_KEY_PREFIX}{worker_id}:*"
    deleted = 0
    cursor = 0
    while True:
        cursor, batch = await redis.scan(
            cursor=cursor,
            match=pattern,
            count=200,
        )
        if batch:
            deleted += await redis.delete(*batch)
        if cursor == 0:
            break
    return int(deleted)


async def _log_audit(
    session: AsyncSession,
    *,
    worker_id: str | None,
    ip: str | None,
    action: str,
    job_id: str | None = None,
    status_code: int | None = None,
    meta: dict | None = None,
) -> None:
    entry = WorkerAuditLog(
        worker_id=worker_id,
        ip=ip,
        action=action,
        job_id=job_id,
        status_code=status_code,
        meta=meta,
        created_at=datetime.now(UTC),
    )
    session.add(entry)
    try:
        from app.services.worker_event_stream import (
            publish as publish_event,
        )

        await publish_event(
            worker_id,
            action=action,
            job_id=job_id,
            status_code=status_code,
            ip=ip,
            meta=meta,
        )
    except Exception:
        logger.debug(
            "worker_event_stream_publish_skipped",
            worker_id=worker_id,
            action=action,
        )
    try:
        from app.core.observability import (
            hmac_auth_failure_observed,
        )

        if action == "auth_fail":
            reason = (
                meta.get("reason")
                if isinstance(meta, dict)
                else None
            ) or "unknown"
            hmac_auth_failure_observed(reason=reason)
    except Exception:
        pass


async def register_worker(
    session: AsyncSession,
    *,
    name: str,
    profile: str,
    allowed_ip_cidrs: list[str] | None = None,
    allowed_profiles: list[str] | None = None,
    max_concurrent_jobs: int = 1,
) -> tuple[ComputeWorker, str]:
    """Create a worker and return ``(worker, raw_secret)``.

    The raw secret is returned once — it is not stored; only its
    SHA-256 hash ends up in the database. ``allowed_ip_cidrs``
    must already be normalized (use
    `dotsound_private_core.services.network_policy.normalize_cidrs`
    before calling).
    """
    worker_id = f"w_{secrets.token_hex(10)}"
    secret = secrets.token_urlsafe(36)
    token_hash = _hash_token(secret)
    worker = ComputeWorker(
        id=worker_id,
        name=name,
        profile=profile,
        token_hash=token_hash,
        active=True,
        allowed_ip_cidrs=allowed_ip_cidrs or None,
        allowed_profiles=allowed_profiles or None,
        max_concurrent_jobs=max(
            1, int(max_concurrent_jobs or 1)
        ),
    )
    session.add(worker)
    await session.flush()
    return worker, secret


async def verify_worker_request(
    session: AsyncSession,
    *,
    worker_id: str,
    timestamp: str,
    nonce: str,
    signature_hex: str,
    method: str,
    path: str,
    body: bytes,
    client_ip: str | None,
    signature_version: str | None = None,
) -> ComputeWorker:
    if (
        not worker_id
        or not timestamp
        or not nonce
        or not signature_hex
    ):
        raise WorkerAuthError("missing_headers")

    if (
        signature_version
        and signature_version != SIGNATURE_VERSION
    ):
        raise WorkerAuthError("unsupported_signature_version")

    try:
        ts_int = int(timestamp)
    except ValueError as exc:
        raise WorkerAuthError("bad_timestamp") from exc
    now_unix = int(time.time())
    if abs(now_unix - ts_int) > _TIMESTAMP_SKEW:
        raise WorkerAuthError("stale_timestamp")

    if not await _check_nonce(worker_id, nonce):
        raise WorkerAuthError("nonce_replay")

    result = await session.execute(
        select(ComputeWorker).where(
            ComputeWorker.id == worker_id
        )
    )
    worker = result.scalar_one_or_none()
    if not worker or not worker.active:
        raise WorkerNotFoundError("unknown_or_inactive")
    if worker.revoked_at is not None:
        raise WorkerNotFoundError("revoked")

    expected = _compute_signature(
        worker.token_hash,
        method,
        path,
        timestamp,
        nonce,
        body,
    )
    if not hmac.compare_digest(expected, signature_hex):
        raise WorkerAuthError("bad_signature")

    if worker.allowed_ip_cidrs and not is_ip_in_cidrs(
        client_ip, worker.allowed_ip_cidrs
    ):
        raise WorkerAuthError("ip_not_allowed")

    now_dt = datetime.now(UTC)
    if (
        worker.suspended_until is not None
        and worker.suspended_until > now_dt
    ):
        raise WorkerAuthError("suspended")

    worker.last_seen_at = now_dt
    if client_ip:
        worker.last_ip = client_ip
    await session.flush()
    return worker


# Mirrors ``lyrics_cascade.TIER_PROFILE_MAP`` job routing keys only
# for worker-facing labels (avoid importing ``lyrics_cascade`` here:
# it pulls ``lyrics_worker`` / Taskiq and can destabilize hot paths).
_WORKER_LABEL_TO_LYRICS_JOB_PROFILE: dict[str, str] = {
    "remote_whisper": "gpu_full",
}


def _expand_profiles_for_lyrics_claim(
    profiles: list[str],
) -> list[str]:
    """Map admin tier-style worker labels onto ``LyricsJob.profile``.

    ``lyrics_cascade.TIER_PROFILE_MAP`` stores ``remote_whisper`` tier
    jobs under profile ``gpu_full``. Workers may still be registered
    with ``profile=remote_whisper`` (allowed by admin schema), so we
    union both spellings for the SQL ``IN`` filter.
    """
    out: list[str] = []
    seen: set[str] = set()
    for w in profiles:
        if not isinstance(w, str) or not w.strip():
            continue
        w = w.strip()
        mapped = _WORKER_LABEL_TO_LYRICS_JOB_PROFILE.get(w, w)
        for c in (w, mapped):
            if c not in seen:
                seen.add(c)
                out.append(c)
    return out


def worker_can_run_lyrics_profile(
    worker: ComputeWorker,
    job_profile: str,
) -> bool:
    profiles = _expand_profiles_for_lyrics_claim(
        list(worker.allowed_profiles or [worker.profile])
    )
    return job_profile in profiles


async def claim_next_job(
    session: AsyncSession,
    *,
    worker: ComputeWorker,
) -> LyricsJob | None:
    """Atomically move the oldest queued job to running.

    Per-worker scope (revoke / suspend / max_concurrent_jobs /
    allowed_profiles) is enforced before any DB UPDATE so a
    suspended worker walks away without holding row locks.
    Atomic ordering uses ``FOR UPDATE SKIP LOCKED`` on PostgreSQL;
    SQLite tests fall back to plain SELECT (single-threaded).
    """
    now = datetime.now(UTC)
    if worker.revoked_at is not None:
        return None
    if worker_claims_blocked(worker, now=now):
        return None
    if (
        worker.suspended_until is not None
        and worker.suspended_until > now
    ):
        return None

    in_flight_q = (
        select(func.count())
        .select_from(LyricsJob)
        .where(
            LyricsJob.routed_to_worker == worker.id,
            LyricsJob.status == "running",
        )
    )
    in_flight = (
        await session.execute(in_flight_q)
    ).scalar() or 0
    max_concurrent = max(
        1, int(worker.max_concurrent_jobs or 1)
    )
    if in_flight >= max_concurrent:
        logger.info(
            "lyrics_claim_skipped_at_capacity",
            worker_id=worker.id,
            in_flight=int(in_flight),
            max_concurrent=max_concurrent,
        )
        return None

    profiles = _expand_profiles_for_lyrics_claim(
        list(worker.allowed_profiles or [worker.profile]),
    )
    if not profiles:
        return None

    select_stmt = (
        select(LyricsJob.id)
        .where(
            LyricsJob.status == "queued",
            LyricsJob.profile.in_(profiles),
            or_(
                LyricsJob.pinned_worker_id.is_(None),
                LyricsJob.pinned_worker_id == worker.id,
            ),
        )
        .order_by(
            LyricsJob.queue_priority.desc(),
            LyricsJob.created_at.asc(),
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

    deadline = now + timedelta(
        minutes=_DEFAULT_LEASE_MINUTES
    )
    update_stmt = (
        update(LyricsJob)
        .where(
            LyricsJob.id == job_id,
            LyricsJob.status == "queued",
        )
        .values(
            status="running",
            routed_to_worker=worker.id,
            pinned_worker_id=None,
            started_at=now,
            deadline_at=deadline,
            attempts=LyricsJob.attempts + 1,
        )
        .returning(LyricsJob)
        .execution_options(
            synchronize_session="fetch",
        )
    )
    res = await session.execute(update_stmt)
    return res.scalars().first()


async def mark_job_result(
    session: AsyncSession,
    *,
    job: LyricsJob,
    duration_ms: int,
) -> None:
    job.status = "done"
    job.finished_at = datetime.now(UTC)
    job.duration_ms = int(duration_ms)
    attempts = list(job.tier_attempts or [])
    if attempts:
        last = dict(attempts[-1])
        if last.get("status") in {"queued", "running"}:
            last["finished_at"] = job.finished_at.isoformat()
            last["status"] = "success"
            attempts[-1] = last
            job.tier_attempts = attempts
    try:
        from app.core.observability import (
            lyrics_job_observed,
        )

        lyrics_job_observed(
            tier=(
                job.current_tier
                or job.profile
                or "remote_whisper"
            ),
            status="success",
            duration_seconds=max(
                0.0, float(duration_ms) / 1000.0
            ),
        )
    except Exception:
        pass


async def mark_job_failed(
    session: AsyncSession,
    *,
    job: LyricsJob,
    reason: str,
) -> None:
    job.status = "failed"
    job.finished_at = datetime.now(UTC)
    job.error = (reason or "")[:1024]
    try:
        from app.core.observability import (
            lyrics_job_observed,
        )

        duration_seconds = 0.0
        if job.started_at is not None:
            started = job.started_at
            if started.tzinfo is None:
                started = started.replace(
                    tzinfo=UTC
                )
            duration_seconds = (
                job.finished_at - started
            ).total_seconds()
        lyrics_job_observed(
            tier=(
                job.current_tier
                or job.profile
                or "unknown"
            ),
            status="failed",
            duration_seconds=duration_seconds,
        )
    except Exception:
        pass


def generate_single_use_token(
    job_id: str, worker_id: str, ttl_s: int = _OTT_TTL
) -> str:
    """Create a short-lived signed token tying one audio blob to
    one job+worker pair. Single-use semantics are enforced at
    redemption time via Redis SET NX EX; here we just sign.

    Default TTL is 5 minutes (was 15) — workers should download
    immediately after claim, not later.
    """
    exp = int(time.time()) + int(ttl_s)
    raw = f"{job_id}:{worker_id}:{exp}"
    sig = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{exp}.{sig}"


async def validate_ott_token(
    token: str,
    job_id: str,
    worker_id: str,
    client_ip: str | None,
    expected_ip: str | None,
) -> int | None:
    """Check OTT signature, expiry, and IP. Returns ``exp`` or None.

    Does **not** consume the token. Call :func:`consume_ott_by_exp`
    only after a download URL is ready, so a failed S3/SC resolution
    does not burn a one-shot OTT.
    """
    try:
        exp_str, sig = token.split(".", 1)
        exp = int(exp_str)
    except (ValueError, AttributeError):
        return None
    now_unix = int(time.time())
    if exp < now_unix:
        return None
    raw = f"{job_id}:{worker_id}:{exp}"
    expected = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None

    if expected_ip and client_ip and (
        client_ip != expected_ip
    ):
        return None
    return exp


async def consume_ott_by_exp(
    exp: int,
    job_id: str,
    worker_id: str,
) -> bool:
    """Record single-use OTT in Redis. Same key layout as before."""
    now_unix = int(time.time())
    if exp < now_unix:
        return False
    redis = get_redis_client()
    key = f"{OTT_KEY_PREFIX}{job_id}:{worker_id}:{exp}"
    ttl = max(1, exp - now_unix)
    claimed = await redis.set(
        key, "1", ex=ttl, nx=True
    )
    return bool(claimed)


async def verify_and_consume_ott(
    token: str,
    job_id: str,
    worker_id: str,
    client_ip: str | None,
    expected_ip: str | None,
) -> bool:
    """Verify an OTT, single-use claim it, and pin to ``client_ip``.

    Returns True only if signature is valid, not expired, not
    previously redeemed, and the request IP matches the worker's
    last seen IP at claim time. False on any failure (caller maps
    to 404 for opacity).
    """
    exp = await validate_ott_token(
        token, job_id, worker_id, client_ip, expected_ip
    )
    if exp is None:
        return False
    return await consume_ott_by_exp(exp, job_id, worker_id)


def verify_single_use_token(
    token: str, job_id: str, worker_id: str
) -> bool:
    """Backward-compatible helper: verifies signature only.

    Single-use semantics now live in `verify_and_consume_ott`.
    Kept for callers that need a quick signature pre-check before
    hitting Redis.
    """
    try:
        exp_str, sig = token.split(".", 1)
        exp = int(exp_str)
    except (ValueError, AttributeError):
        return False
    if exp < int(time.time()):
        return False
    raw = f"{job_id}:{worker_id}:{exp}"
    expected = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig)


def validate_lyrics_result(payload: dict) -> dict:
    """Raise ValueError if a worker result payload is unsafe.

    Returns a sanitized copy suitable for persisting. Pure
    transport: no domain knowledge here.
    """
    import html

    if not isinstance(payload, dict):
        raise ValueError("payload_not_object")
    text = payload.get("plain_text") or ""
    if not isinstance(text, str):
        raise ValueError("plain_text_type")
    if len(text) > 20_000:
        raise ValueError("plain_text_too_long")
    plain_text = html.escape(text, quote=False)[:20_000]

    synced_raw = payload.get("synced_lines")
    synced: list[dict] | None = None
    if synced_raw is not None:
        if not isinstance(synced_raw, list):
            raise ValueError("synced_lines_type")
        if len(synced_raw) > 2_000:
            raise ValueError("synced_lines_too_long")
        prev_ms = -1
        clean: list[dict] = []
        for item in synced_raw:
            if not isinstance(item, dict):
                continue
            try:
                time_ms = int(item.get("time_ms") or 0)
                line_text = str(item.get("text") or "")[:500]
                conf = float(item.get("confidence") or 0.0)
            except (TypeError, ValueError):
                continue
            if time_ms < 0:
                continue
            if time_ms < prev_ms:
                time_ms = prev_ms
            prev_ms = time_ms
            entry: dict = {
                "time_ms": time_ms,
                "text": html.escape(line_text, quote=False),
                "confidence": max(0.0, min(1.0, conf)),
            }
            wts = item.get("word_times")
            if isinstance(wts, list) and wts:
                clean_wts: list[dict] = []
                for w in wts[:200]:
                    if not isinstance(w, dict):
                        continue
                    try:
                        w_text = str(w.get("text") or "")[
                            :200
                        ]
                        w_start = int(
                            w.get("start_ms") or 0
                        )
                        w_dur = int(w.get("dur_ms") or 0)
                        w_conf = float(
                            w.get("confidence") or 0.0
                        )
                    except (TypeError, ValueError):
                        continue
                    if w_start < 0 or w_dur < 0:
                        continue
                    clean_wts.append(
                        {
                            "text": html.escape(
                                w_text, quote=False
                            ),
                            "start_ms": w_start,
                            "dur_ms": w_dur,
                            "confidence": max(
                                0.0, min(1.0, w_conf)
                            ),
                        }
                    )
                if clean_wts:
                    entry["word_times"] = clean_wts
            clean.append(entry)
        synced = clean or None

    sync_quality = payload.get("sync_quality")
    if sync_quality not in {None, "line", "word", "none"}:
        sync_quality = None
    sync_profile = payload.get("sync_profile")
    if sync_profile not in {None, "cpu_light", "gpu_full"}:
        sync_profile = None

    asr_parsed: list[dict[str, object]] | None = None
    raw_asr = payload.get("asr_timed_words")
    if raw_asr is not None:
        if not isinstance(raw_asr, list) or len(raw_asr) > 80_000:
            raise ValueError("asr_timed_words_invalid")
        asr_parsed = []
        for item in raw_asr:
            if not isinstance(item, dict):
                continue
            try:
                t = float(item.get("t", 0))
            except (TypeError, ValueError):
                continue
            w = str(item.get("w", "")).strip()[:200]
            if t < 0.0 or not w:
                continue
            asr_parsed.append({"t": t, "w": w})
        asr_parsed = asr_parsed or None
    audio_seconds: float | None = None
    raw_audio_seconds = payload.get("audio_seconds")
    if raw_audio_seconds is not None:
        try:
            parsed_audio_seconds = float(raw_audio_seconds)
        except (TypeError, ValueError):
            parsed_audio_seconds = 0.0
        if parsed_audio_seconds > 0.0:
            audio_seconds = parsed_audio_seconds

    return {
        "plain_text": plain_text,
        "synced_lines": synced,
        "sync_quality": sync_quality,
        "sync_profile": sync_profile,
        "audio_sha256": payload.get("audio_sha256"),
        "asr_timed_words": asr_parsed,
        "audio_seconds": audio_seconds,
    }


def attribution_for_remote_worker_result(
    *,
    current_tier: str | None,
    synced_lines: list[dict] | None,
    sync_profile: str | None,
) -> tuple[str | None, str | None]:
    """Labels for :class:`TrackLyrics` ``source_name`` and
    ``sync_source_name`` when a compute worker returns ASR text
    (same pipeline as in-app ``faster-whisper``).
    """
    t = (current_tier or "").strip()
    if t in ("", "remote_whisper"):
        base = "faster-whisper"
    else:
        base = f"ASR ({t})"
    if not synced_lines:
        return base, None
    if sync_profile == "gpu_full":
        return base, f"{base} (GPU)"
    if sync_profile == "cpu_light":
        return base, f"{base} (CPU)"
    return base, base


__all__ = [
    "SIGNATURE_VERSION",
    "WorkerAuthError",
    "WorkerNotFoundError",
    "claim_next_job",
    "generate_single_use_token",
    "invalidate_worker_nonces",
    "mark_job_failed",
    "mark_job_result",
    "register_worker",
    "attribution_for_remote_worker_result",
    "validate_lyrics_result",
    "validate_ott_token",
    "consume_ott_by_exp",
    "verify_and_consume_ott",
    "verify_single_use_token",
    "verify_worker_request",
    "_log_audit",
]
