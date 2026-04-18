"""Audio-compute worker lifecycle.

Worker registration, HMAC-signed request verification, heartbeat,
job claim/result/fail, and audit logging. The worker daemon lives
in the private core; everything here is transport.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import get_redis_client
from app.models.compute_worker import ComputeWorker
from app.models.lyrics_job import LyricsJob
from app.models.worker_audit import WorkerAuditLog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

NONCE_KEY_PREFIX = "worker:nonce:"
_NONCE_TTL = 300
_TIMESTAMP_SKEW = 60


class WorkerAuthError(Exception):
    pass


class WorkerNotFoundError(Exception):
    pass


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
    ).encode("utf-8")


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
        created_at=datetime.now(timezone.utc),
    )
    session.add(entry)


async def register_worker(
    session: AsyncSession,
    *,
    name: str,
    profile: str,
) -> tuple[ComputeWorker, str]:
    """Create a worker and return ``(worker, raw_secret)``.

    The raw secret is returned once — it is not stored; only its
    SHA-256 hash ends up in the database.
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
) -> ComputeWorker:
    if not worker_id or not timestamp or not nonce or not signature_hex:
        raise WorkerAuthError("missing_headers")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise WorkerAuthError("bad_timestamp")
    now = int(time.time())
    if abs(now - ts_int) > _TIMESTAMP_SKEW:
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

    worker.last_seen_at = datetime.now(timezone.utc)
    if client_ip:
        worker.last_ip = client_ip
    await session.flush()
    return worker


async def claim_next_job(
    session: AsyncSession,
    *,
    worker: ComputeWorker,
) -> LyricsJob | None:
    """Atomically move a queued job to running for the worker."""
    deadline = datetime.now(timezone.utc) + timedelta(
        minutes=10
    )
    now = datetime.now(timezone.utc)
    stmt = (
        update(LyricsJob)
        .where(
            LyricsJob.status == "queued",
            LyricsJob.profile == worker.profile,
        )
        .values(
            status="running",
            routed_to_worker=worker.id,
            started_at=now,
            deadline_at=deadline,
            attempts=LyricsJob.attempts + 1,
        )
        .returning(LyricsJob)
        .execution_options(
            synchronize_session="fetch",
        )
    )
    res = await session.execute(stmt)
    return res.scalars().first()


async def mark_job_result(
    session: AsyncSession,
    *,
    job: LyricsJob,
    duration_ms: int,
) -> None:
    job.status = "done"
    job.finished_at = datetime.now(timezone.utc)
    job.duration_ms = int(duration_ms)


async def mark_job_failed(
    session: AsyncSession,
    *,
    job: LyricsJob,
    reason: str,
) -> None:
    job.status = "failed"
    job.finished_at = datetime.now(timezone.utc)
    job.error = (reason or "")[:1024]


def generate_single_use_token(
    job_id: str, worker_id: str, ttl_s: int = 900
) -> str:
    """Create a short-lived signed token tying one audio blob to
    one job+worker pair.
    """
    exp = int(time.time()) + int(ttl_s)
    raw = f"{job_id}:{worker_id}:{exp}"
    sig = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{exp}.{sig}"


def verify_single_use_token(
    token: str, job_id: str, worker_id: str
) -> bool:
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

    return {
        "plain_text": plain_text,
        "synced_lines": synced,
        "sync_quality": sync_quality,
        "sync_profile": sync_profile,
        "audio_sha256": payload.get("audio_sha256"),
    }


__all__ = [
    "WorkerAuthError",
    "WorkerNotFoundError",
    "claim_next_job",
    "generate_single_use_token",
    "mark_job_failed",
    "mark_job_result",
    "register_worker",
    "validate_lyrics_result",
    "verify_single_use_token",
    "verify_worker_request",
    "_log_audit",
]
