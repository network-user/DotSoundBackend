"""Internal endpoints for audio-compute workers.

These are never exposed to end users. Every request is verified
via HMAC + nonce replay protection (see compute_worker_service)
and the path is gated by `InternalApiAllowlistMiddleware`. Worker
provisioning happens offline via admin UI; there is no public
self-registration endpoint here by design.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.config import settings
from app.dependencies import get_db
from app.models.track import Track
from app.repositories.audio_compute import (
    AudioComputeRepository,
)
from app.repositories.lyrics import LyricsRepository
from app.services import compute_worker_service as cws
from app.services import worker_rate_limit as rl
from app.services.lyrics_worker import (
    set_lyrics_progress,
    store_partial_synced,
    store_partial_text,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

router = APIRouter(
    prefix="/internal/audio-compute",
    tags=["audio-compute"],
)


def _client_ip(request: Request) -> str | None:
    return (
        request.client.host if request.client else None
    )


async def _enforce_rate_limit(
    request: Request,
    session: AsyncSession,
    *,
    worker_id: str,
    action: str,
) -> None:
    """Wrap rate-limit check with HTTP 429 mapping."""
    try:
        await rl.check_and_consume(
            session,
            worker_id=worker_id,
            action=action,
            audit_ip=_client_ip(request),
        )
    except rl.WorkerRateLimitExceeded:
        raise HTTPException(status_code=429)


async def _verify(
    request: Request, session: AsyncSession
) -> "tuple[object, bytes]":
    body = await request.body()
    try:
        worker = await cws.verify_worker_request(
            session,
            worker_id=request.headers.get(
                "X-Worker-Id", ""
            ),
            timestamp=request.headers.get(
                "X-Timestamp", ""
            ),
            nonce=request.headers.get("X-Nonce", ""),
            signature_hex=request.headers.get(
                "X-Worker-Signature", ""
            ),
            method=request.method,
            path=request.url.path,
            body=body,
            client_ip=_client_ip(request),
            signature_version=request.headers.get(
                "X-Worker-Signature-Version"
            ),
        )
    except cws.WorkerNotFoundError:
        await cws._log_audit(
            session,
            worker_id=request.headers.get("X-Worker-Id"),
            ip=_client_ip(request),
            action="auth_fail",
            status_code=404,
        )
        await session.commit()
        raise HTTPException(status_code=404)
    except cws.WorkerAuthError as exc:
        await cws._log_audit(
            session,
            worker_id=request.headers.get("X-Worker-Id"),
            ip=_client_ip(request),
            action="auth_fail",
            status_code=401,
            meta={"reason": str(exc)},
        )
        await session.commit()
        raise HTTPException(status_code=401)

    return worker, body


@router.post("/workers/heartbeat")
async def heartbeat(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    worker, _ = await _verify(request, session)
    await _enforce_rate_limit(
        request,
        session,
        worker_id=worker.id,
        action="heartbeat",
    )
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=_client_ip(request),
        action="heartbeat",
        status_code=200,
    )
    await session.commit()
    return {
        "status": "ok",
        "server_time": int(
            datetime.now(timezone.utc).timestamp()
        ),
    }


@router.post(
    "/jobs/claim",
    response_model=None,
)
async def claim(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> Response:
    worker, _ = await _verify(request, session)
    await _enforce_rate_limit(
        request,
        session,
        worker_id=worker.id,
        action="claim",
    )
    job = await cws.claim_next_job(session, worker=worker)
    if job is None:
        await cws._log_audit(
            session,
            worker_id=worker.id,
            ip=_client_ip(request),
            action="claim_empty",
            status_code=204,
        )
        await session.commit()
        # 204 must have no body; ``JSONResponse(..., content=None)``
        # can confuse Content-Length under uvicorn (ASGI).
        return Response(
            status_code=204
        )

    token = cws.generate_single_use_token(job.id, worker.id)
    payload = {
        "job_id": job.id,
        "track_id": job.track_id,
        "profile": job.profile,
        "progress_id": job.progress_id,
        "audio_sha256": job.audio_sha256,
        "correlation_id": job.id,
        "current_tier": job.current_tier,
        "deadline_at": job.deadline_at.isoformat()
        if job.deadline_at
        else None,
        "audio_url": (
            f"/api/v1/internal/audio-compute/audio/{job.id}"
            f"?ott={token}"
        ),
    }
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=_client_ip(request),
        action="claim_ok",
        job_id=job.id,
        status_code=200,
    )
    await session.commit()
    return JSONResponse(
        status_code=200,
        content=payload,
        headers={"X-Correlation-Id": job.id},
    )


@router.post("/jobs/{job_id}/progress")
async def job_progress(
    job_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    worker, body = await _verify(request, session)
    await _enforce_rate_limit(
        request,
        session,
        worker_id=worker.id,
        action="progress",
    )
    try:
        event = json.loads(body or b"{}")
    except (TypeError, ValueError):
        raise HTTPException(status_code=400)

    repo = AudioComputeRepository(session)
    job = await repo.get_job_for_worker(job_id, worker.id)
    if job is None:
        raise HTTPException(status_code=404)

    stage = event.get("stage")
    percent = event.get("percent")
    log_msg = event.get("message")
    await set_lyrics_progress(
        job.progress_id,
        stage=stage,
        log_line=log_msg,
        percent=percent
        if isinstance(percent, int)
        else None,
    )

    partial_text = event.get("partial_text")
    if isinstance(partial_text, str) and partial_text:
        await store_partial_text(
            job.progress_id, partial_text
        )
    partial_sync = event.get("partial_synced_lines")
    if isinstance(partial_sync, list) and partial_sync:
        await store_partial_synced(
            job.progress_id, partial_sync
        )

    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=_client_ip(request),
        action="progress",
        job_id=job.id,
        status_code=200,
    )
    await session.commit()
    return {"status": "ok"}


@router.post("/jobs/{job_id}/result")
async def job_result(
    job_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    worker, body = await _verify(request, session)
    await _enforce_rate_limit(
        request,
        session,
        worker_id=worker.id,
        action="result",
    )
    try:
        payload = json.loads(body or b"{}")
    except (TypeError, ValueError):
        raise HTTPException(status_code=400)

    repo = AudioComputeRepository(session)
    job = await repo.get_job_for_worker(job_id, worker.id)
    if job is None:
        raise HTTPException(status_code=404)
    if job.status not in {"running", "queued"}:
        raise HTTPException(status_code=409)

    if job.audio_sha256 and payload.get("audio_sha256"):
        if job.audio_sha256 != payload.get("audio_sha256"):
            await cws._log_audit(
                session,
                worker_id=worker.id,
                ip=_client_ip(request),
                action="audio_sha_mismatch",
                job_id=job.id,
                status_code=400,
            )
            await session.commit()
            raise HTTPException(status_code=400)

    try:
        clean = cws.validate_lyrics_result(payload)
    except ValueError as exc:
        await cws._log_audit(
            session,
            worker_id=worker.id,
            ip=_client_ip(request),
            action="result_invalid",
            job_id=job.id,
            status_code=422,
            meta={"reason": str(exc)},
        )
        await session.commit()
        raise HTTPException(status_code=422)

    lyrics_repo = LyricsRepository(session)
    existing = await lyrics_repo.get_by_track_id(
        job.track_id
    )

    plain_out = clean["plain_text"]
    synced_out = clean["synced_lines"]
    sq_out = clean["sync_quality"]
    sp_out = clean["sync_profile"]
    sn_out: str | None
    ssn_out: str | None

    use_catalog = (
        existing is not None
        and existing.source == "auto"
        and (existing.plain_text or "").strip()
        and clean.get("asr_timed_words")
    )
    aligned: list | None = None
    if use_catalog:
        try:
            from dotsound_private_core.services.lyrics_provider import (
                SyncedLine,
                align_text_to_precomputed_asr_timed_words,
            )

            tw_list = clean["asr_timed_words"] or []
            tw_pairs: list[tuple[float, str]] = [
                (float(x["t"]), str(x["w"]))
                for x in tw_list
            ]

            def _align() -> list[SyncedLine] | None:
                audio_seconds = float(
                    clean.get("audio_seconds") or 0.0
                )
                audio_duration_ms = (
                    int(audio_seconds * 1000)
                    if audio_seconds > 0.0
                    else 0
                )
                return align_text_to_precomputed_asr_timed_words(
                    existing.plain_text,  # type: ignore[arg-type]
                    tw_pairs,
                    audio_duration_ms=audio_duration_ms,
                )

            aligned = await asyncio.to_thread(_align)
        except Exception:
            logger.exception(
                "remote_lyrics_catalog_align_failed",
                job_id=job.id,
            )
            aligned = None

    if aligned:
        assert existing is not None
        plain_out = existing.plain_text
        synced_out = [
            {
                "time_ms": int(sl.time_ms),
                "text": sl.text,
                "confidence": float(
                    getattr(sl, "confidence", 0.0) or 0.0
                ),
            }
            for sl in aligned
            if (sl.text or "").strip()
        ] or None
        sq_out = "line"
        sp_out = clean.get("sync_profile")
        base = (existing.source_name or "").strip() or "Catalog"
        sn_out = base
        sp_lbl = sp_out or "asr"
        ssn_out = f"faster-whisper (aligned, {sp_lbl})"
        logger.info(
            "remote_lyrics_catalog_align_applied",
            job_id=job.id,
            aligned_lines=len(synced_out or []),
            asr_words=len(clean.get("asr_timed_words") or []),
            audio_seconds=clean.get("audio_seconds"),
        )
    else:
        if use_catalog:
            logger.info(
                "remote_lyrics_catalog_align_skipped",
                job_id=job.id,
                asr_words=len(clean.get("asr_timed_words") or []),
                audio_seconds=clean.get("audio_seconds"),
            )
        sn_out, ssn_out = cws.attribution_for_remote_worker_result(
            current_tier=job.current_tier,
            synced_lines=synced_out,
            sync_profile=sp_out,
        )

    await lyrics_repo.create_or_update(
        track_id=job.track_id,
        plain_text=plain_out,
        source="auto",
        synced_lines=synced_out,
        sync_quality=sq_out,
        sync_profile=sp_out,
        source_name=sn_out,
        sync_source_name=ssn_out,
    )

    started = job.started_at or job.created_at
    duration_ms = 0
    if started:
        started_aware = started
        if started_aware.tzinfo is None:
            started_aware = started_aware.replace(
                tzinfo=timezone.utc
            )
        duration_ms = int(
            (
                datetime.now(timezone.utc)
                - started_aware
            ).total_seconds()
            * 1000
        )
    await cws.mark_job_result(
        session, job=job, duration_ms=duration_ms
    )

    audio_seconds = float(
        payload.get("audio_seconds") or 0
    )
    try:
        from app.services.compute_anomaly_service import (
            record_remote_result,
        )

        await record_remote_result(
            session,
            worker_id=worker.id,
            job_id=job.id,
            audio_seconds=audio_seconds,
            processing_seconds=(
                duration_ms / 1000.0
            ),
            plain_text=plain_out,
        )
    except Exception:
        logger.exception(
            "anomaly_check_failed",
            job_id=job.id,
            worker_id=worker.id,
        )

    await set_lyrics_progress(
        job.progress_id,
        stage="saving",
        terminal_state="found",
        percent=100,
        log_line="remote worker result saved",
    )
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=_client_ip(request),
        action="result_ok",
        job_id=job.id,
        status_code=200,
    )
    await session.commit()
    return {"status": "ok"}


@router.post("/jobs/{job_id}/fail")
async def job_fail(
    job_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    worker, body = await _verify(request, session)
    await _enforce_rate_limit(
        request,
        session,
        worker_id=worker.id,
        action="fail",
    )
    try:
        payload = json.loads(body or b"{}")
    except (TypeError, ValueError):
        payload = {}
    reason = str(payload.get("reason") or "worker_failure")[:256]

    repo = AudioComputeRepository(session)
    job = await repo.get_job_for_worker(job_id, worker.id)
    if job is None:
        raise HTTPException(status_code=404)

    try:
        from app.services.lyrics_cascade import (
            handle_tier_failure,
        )

        will_fallback = await handle_tier_failure(
            session, job=job, reason=reason
        )
    except ImportError:
        will_fallback = False

    if not will_fallback:
        await cws.mark_job_failed(
            session, job=job, reason=reason
        )
        await set_lyrics_progress(
            job.progress_id,
            stage="error",
            terminal_state="error",
            log_line=f"remote worker failed: {reason}",
        )
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=_client_ip(request),
        action="result_fail",
        job_id=job.id,
        status_code=200,
        meta={
            "reason": reason,
            "fallback": bool(will_fallback),
        },
    )
    await session.commit()
    return {
        "status": "ok",
        "fallback": bool(will_fallback),
    }


@router.get("/audio/{job_id}")
async def download_audio(
    job_id: str,
    ott: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    worker_id = request.headers.get("X-Worker-Id", "")
    if not worker_id or not ott:
        raise HTTPException(status_code=404)

    try:
        await rl.check_and_consume(
            session,
            worker_id=worker_id,
            action="audio",
            audit_ip=_client_ip(request),
        )
    except rl.WorkerRateLimitExceeded:
        raise HTTPException(status_code=429)

    repo = AudioComputeRepository(session)
    job = await repo.get_job_for_worker(job_id, worker_id)
    if (
        job is None
        or job.status != "running"
    ):
        raise HTTPException(status_code=404)

    expected_ip = job.routed_to_worker and (
        await repo.get_worker(job.routed_to_worker)
    )
    pinned_ip = (
        expected_ip.last_ip if expected_ip else None
    )
    exp = await cws.validate_ott_token(
        ott,
        job.id,
        worker_id,
        client_ip=_client_ip(request),
        expected_ip=pinned_ip,
    )
    if exp is None:
        await cws._log_audit(
            session,
            worker_id=worker_id,
            ip=_client_ip(request),
            action="ott_fail",
            job_id=job.id,
            status_code=404,
        )
        await session.commit()
        raise HTTPException(status_code=404)

    file_key = await repo.get_track_file_key(
        job.track_id
    )
    payload: dict
    if file_key:
        try:
            presigned = await s3.get_presigned_url(
                file_key
            )
        except Exception as exc:
            logger.warning(
                "audio_presign_failed",
                job_id=job_id,
                track_id=job.track_id,
                err=str(exc),
            )
            await session.commit()
            raise HTTPException(
                status_code=503
            ) from exc
        payload = {"url": presigned}
    else:
        track = await session.get(Track, job.track_id)
        if not track or not getattr(
            track, "sc_url", None
        ):
            logger.warning(
                "audio_download_no_file_key",
                job_id=job_id,
                track_id=job.track_id,
            )
            await session.commit()
            raise HTTPException(status_code=404)
        if not settings.sc_client_id:
            logger.warning(
                "audio_download_sc_no_client_id",
                job_id=job_id,
                track_id=job.track_id,
            )
            await session.commit()
            raise HTTPException(
                status_code=503,
                detail="SoundCloud is not configured",
            )
        from app.services.soundcloud_service import (
            SoundCloudService,
        )

        sc = SoundCloudService(
            settings.sc_client_id, session
        )
        try:
            stream_url, protocol = await sc.get_stream_info(
                track.sc_url
            )
        except HTTPException:
            await session.commit()
            raise
        except Exception as exc:
            logger.warning(
                "audio_download_sc_failed",
                job_id=job_id,
                track_id=job.track_id,
                err=str(exc),
            )
            await session.commit()
            raise HTTPException(
                status_code=503
            ) from exc
        payload = {
            "url": stream_url,
            "stream_protocol": protocol,
        }

    if not await cws.consume_ott_by_exp(
        exp, job.id, worker_id
    ):
        await cws._log_audit(
            session,
            worker_id=worker_id,
            ip=_client_ip(request),
            action="ott_fail",
            job_id=job.id,
            status_code=404,
        )
        await session.commit()
        raise HTTPException(status_code=404)

    return JSONResponse(
        status_code=200,
        content=payload,
    )
