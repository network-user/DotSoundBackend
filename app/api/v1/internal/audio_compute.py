"""Internal endpoints for audio-compute workers.

These are never exposed to end users. Every request is verified
via HMAC + nonce replay protection (see compute_worker_service).
Worker provisioning happens offline via admin UI; there is no
public self-registration endpoint here by design.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.lyrics_job import LyricsJob
from app.repositories.lyrics import LyricsRepository
from app.services import compute_worker_service as cws
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
            client_ip=request.client.host
            if request.client
            else None,
        )
    except cws.WorkerNotFoundError:
        await cws._log_audit(
            session,
            worker_id=request.headers.get("X-Worker-Id"),
            ip=request.client.host
            if request.client
            else None,
            action="auth_fail",
            status_code=404,
        )
        await session.commit()
        raise HTTPException(status_code=404)
    except cws.WorkerAuthError as exc:
        await cws._log_audit(
            session,
            worker_id=request.headers.get("X-Worker-Id"),
            ip=request.client.host
            if request.client
            else None,
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
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=request.client.host if request.client else None,
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


@router.post("/jobs/claim")
async def claim(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    worker, _ = await _verify(request, session)
    job = await cws.claim_next_job(session, worker=worker)
    if job is None:
        await cws._log_audit(
            session,
            worker_id=worker.id,
            ip=request.client.host
            if request.client
            else None,
            action="claim_empty",
            status_code=204,
        )
        await session.commit()
        return JSONResponse(
            status_code=204, content=None
        )

    token = cws.generate_single_use_token(job.id, worker.id)
    payload = {
        "job_id": job.id,
        "track_id": job.track_id,
        "profile": job.profile,
        "progress_id": job.progress_id,
        "audio_sha256": job.audio_sha256,
        "deadline_at": job.deadline_at.isoformat()
        if job.deadline_at
        else None,
        "audio_url": (
            f"/internal/audio-compute/audio/{job.id}"
            f"?ott={token}"
        ),
    }
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=request.client.host if request.client else None,
        action="claim_ok",
        job_id=job.id,
        status_code=200,
    )
    await session.commit()
    return JSONResponse(status_code=200, content=payload)


@router.post("/jobs/{job_id}/progress")
async def job_progress(
    job_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    worker, body = await _verify(request, session)
    try:
        event = json.loads(body or b"{}")
    except (TypeError, ValueError):
        raise HTTPException(status_code=400)

    result = await session.execute(
        select(LyricsJob).where(LyricsJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job or job.routed_to_worker != worker.id:
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
        ip=request.client.host if request.client else None,
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
    try:
        payload = json.loads(body or b"{}")
    except (TypeError, ValueError):
        raise HTTPException(status_code=400)

    result_q = await session.execute(
        select(LyricsJob).where(LyricsJob.id == job_id)
    )
    job = result_q.scalar_one_or_none()
    if not job or job.routed_to_worker != worker.id:
        raise HTTPException(status_code=404)
    if job.status not in {"running", "queued"}:
        raise HTTPException(status_code=409)

    if job.audio_sha256 and payload.get("audio_sha256"):
        if job.audio_sha256 != payload.get("audio_sha256"):
            await cws._log_audit(
                session,
                worker_id=worker.id,
                ip=request.client.host
                if request.client
                else None,
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
            ip=request.client.host
            if request.client
            else None,
            action="result_invalid",
            job_id=job.id,
            status_code=422,
            meta={"reason": str(exc)},
        )
        await session.commit()
        raise HTTPException(status_code=422)

    repo = LyricsRepository(session)
    await repo.create_or_update(
        track_id=job.track_id,
        plain_text=clean["plain_text"],
        source="auto",
        synced_lines=clean["synced_lines"],
        sync_quality=clean["sync_quality"],
        sync_profile=clean["sync_profile"],
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
                datetime.now(timezone.utc) - started_aware
            ).total_seconds()
            * 1000
        )
    await cws.mark_job_result(
        session, job=job, duration_ms=duration_ms
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
        ip=request.client.host if request.client else None,
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
    try:
        payload = json.loads(body or b"{}")
    except (TypeError, ValueError):
        payload = {}
    reason = str(payload.get("reason") or "worker_failure")[:256]

    result = await session.execute(
        select(LyricsJob).where(LyricsJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job or job.routed_to_worker != worker.id:
        raise HTTPException(status_code=404)

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
        ip=request.client.host if request.client else None,
        action="result_fail",
        job_id=job.id,
        status_code=200,
        meta={"reason": reason},
    )
    await session.commit()
    return {"status": "ok"}


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

    result = await session.execute(
        select(LyricsJob).where(LyricsJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if (
        not job
        or job.routed_to_worker != worker_id
        or job.status != "running"
    ):
        raise HTTPException(status_code=404)

    if not cws.verify_single_use_token(
        ott, job.id, worker_id
    ):
        raise HTTPException(status_code=404)

    from app.core import s3
    from app.models.track import Track

    track = await session.get(Track, job.track_id)
    if track is None or not track.file_key:
        raise HTTPException(status_code=404)

    presigned = await s3.get_presigned_url(track.file_key)
    return JSONResponse(
        status_code=200,
        content={"url": presigned},
    )
