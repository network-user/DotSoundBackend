from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, StreamingResponse

from app.api.v1.internal.audio_compute import (
    _stream_sc_cdn_to_worker,
)
from app.api.v1.internal.worker_request import (
    client_ip,
    verify_worker_hmac_request,
)
from app.config import settings
from app.core import s3
from app.dependencies import get_db
from app.models.compute_job import ComputeJob
from app.models.track import Track
from app.repositories.audio_compute import (
    AudioComputeRepository,
)
from app.services import compute_job_reaper
from app.services import compute_queue_service as q
from app.services import compute_results_router as crr
from app.services import compute_worker_service as cws
from app.services import worker_rate_limit as rl
from app.services.soundcloud_service import SoundCloudService
from app.services.worker_job_control import (
    merge_heartbeat_control_payload,
)

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/internal/compute",
    tags=["internal-compute"],
)


async def _enforce_rate_limit(
    request: Request,
    session: AsyncSession,
    *,
    worker_id: str,
    action: str,
) -> None:
    try:
        await rl.check_and_consume(
            session,
            worker_id=worker_id,
            action=action,
            audit_ip=client_ip(request),
        )
    except rl.WorkerRateLimitExceeded as exc:
        raise HTTPException(status_code=429) from exc


@router.post("/workers/heartbeat")
async def heartbeat(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    worker, _ = await verify_worker_hmac_request(
        request,
        session,
    )
    await _enforce_rate_limit(
        request,
        session,
        worker_id=worker.id,
        action="heartbeat",
    )
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=client_ip(request),
        action="heartbeat",
        status_code=200,
    )
    ctl = await merge_heartbeat_control_payload(
        worker,
        package_version_header=request.headers.get("X-Worker-Package-Version"),
    )
    await session.commit()
    return {
        "status": "ok",
        "server_time": int(datetime.now(UTC).timestamp()),
        **ctl,
    }


@router.post(
    "/jobs/claim",
    response_model=None,
)
async def claim(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> Response:
    worker, body = await verify_worker_hmac_request(
        request,
        session,
    )
    await _enforce_rate_limit(
        request,
        session,
        worker_id=worker.id,
        action="claim",
    )
    try:
        spec = json.loads(body or b"{}")
    except (TypeError, ValueError) as exc:
        await session.rollback()
        raise HTTPException(status_code=400) from exc
    job_types = spec.get("job_types")
    if not isinstance(job_types, list) or not all(
        isinstance(t, str) for t in job_types
    ):
        await session.rollback()
        raise HTTPException(status_code=400) from None
    if not job_types:
        await session.rollback()
        raise HTTPException(status_code=400) from None
    job_types = [
        jt
        for jt in dict.fromkeys(q.canonical_job_type(t) for t in job_types)
        if jt in q.OFFLOADABLE_JOB_TYPES
    ]
    if not job_types:
        await cws._log_audit(
            session,
            worker_id=worker.id,
            ip=client_ip(request),
            action="compute_claim_empty",
            status_code=204,
        )
        await session.commit()
        return Response(status_code=204)
    job = await q.claim_next(
        session,
        worker_id=worker.id,
        job_types=job_types,
    )
    if job is None:
        await cws._log_audit(
            session,
            worker_id=worker.id,
            ip=client_ip(request),
            action="compute_claim_empty",
            status_code=204,
        )
        await session.commit()
        return Response(status_code=204)
    out: dict[str, Any] = {
        "job_id": job.id,
        "job_type": q.canonical_job_type(job.job_type),
        "target_kind": job.target_kind,
        "target_id": job.target_id,
        "payload": job.payload,
        "feature_version": job.feature_version,
        "claim_deadline_at": (
            job.claim_deadline_at.isoformat()
            if job.claim_deadline_at
            else None
        ),
    }
    if job.job_type in (
        q.JOB_TRACK_AUDIO_FEATURES,
        q.JOB_AUDIO_EMBEDDING,
        q.JOB_TRACK_TRANSCODING,
        q.JOB_TRACK_WAVEFORM,
    ):
        token = cws.generate_single_use_token(job.id, worker.id)
        out["audio_url"] = (
            f"/api/v1/internal/compute/jobs/{job.id}/audio" f"?ott={token}"
        )
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=client_ip(request),
        action="compute_claim_ok",
        job_id=job.id,
        status_code=200,
    )
    await session.commit()
    return JSONResponse(
        status_code=200,
        content=out,
        headers={"X-Correlation-Id": job.id},
    )


@router.get("/jobs/{job_id}/audio")
async def download_job_audio(
    job_id: str,
    ott: str,
    request: Request,
    proxy: bool = Query(False),
    session: AsyncSession = Depends(get_db),
) -> Response:
    worker_id = request.headers.get("X-Worker-Id", "")
    if not worker_id or not ott:
        raise HTTPException(status_code=404)

    try:
        await rl.check_and_consume(
            session,
            worker_id=worker_id,
            action="audio",
            audit_ip=client_ip(request),
        )
    except rl.WorkerRateLimitExceeded as exc:
        raise HTTPException(status_code=429) from exc

    job = await session.get(ComputeJob, job_id)
    if (
        job is None
        or job.claimed_by != worker_id
        or job.status != q.STATUS_CLAIMED
        or job.job_type
        not in (
            q.JOB_TRACK_AUDIO_FEATURES,
            q.JOB_AUDIO_EMBEDDING,
        )
    ):
        raise HTTPException(status_code=404)
    if job.target_kind != q.TARGET_KIND_TRACK or not job.target_id:
        raise HTTPException(status_code=404)
    try:
        track_id = int(job.target_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=404) from exc
    track = await session.get(Track, track_id)
    if not track:
        raise HTTPException(status_code=404)
    repo = AudioComputeRepository(session)
    wrow = await repo.get_worker(worker_id)
    pinned_ip = wrow.last_ip if wrow else None
    exp = await cws.validate_ott_token(
        ott,
        job.id,
        worker_id,
        client_ip=client_ip(request),
        expected_ip=pinned_ip,
    )
    if exp is None:
        await cws._log_audit(
            session,
            worker_id=worker_id,
            ip=client_ip(request),
            action="ott_fail",
            job_id=job.id,
            status_code=404,
        )
        await session.commit()
        raise HTTPException(status_code=404)

    if track.file_key:
        try:
            presigned = await s3.get_presigned_url(track.file_key)
        except Exception as exc:
            log.warning(
                "compute_job_audio_presign_failed",
                job_id=job_id,
                track_id=track_id,
                err=str(exc),
            )
            await session.commit()
            raise HTTPException(status_code=503) from exc
        if proxy:
            if not await cws.consume_ott_by_exp(exp, job.id, worker_id):
                await cws._log_audit(
                    session,
                    worker_id=worker_id,
                    ip=client_ip(request),
                    action="ott_fail",
                    job_id=job.id,
                    status_code=404,
                )
                await session.commit()
                raise HTTPException(status_code=404)
            return RedirectResponse(
                url=presigned,
                status_code=302,
            )
        if not await cws.consume_ott_by_exp(exp, job.id, worker_id):
            await cws._log_audit(
                session,
                worker_id=worker_id,
                ip=client_ip(request),
                action="ott_fail",
                job_id=job.id,
                status_code=404,
            )
            await session.commit()
            raise HTTPException(status_code=404)
        return JSONResponse(
            status_code=200,
            content={"url": presigned},
        )

    sc_stream_url: str | None = None
    stream_protocol: str = ""
    sc_ref: str | None = getattr(track, "sc_url", None)
    if sc_ref and settings.sc_client_id:
        sc = SoundCloudService(settings.sc_client_id, session)
        try:
            sc_stream_url, stream_protocol = await asyncio.wait_for(
                sc.get_stream_info(
                    sc_ref,
                    use_cache=False,
                ),
                timeout=(settings.lyrics_audio_resolve_timeout_seconds),
            )
        except TimeoutError as exc:
            log.warning(
                "compute_job_audio_sc_resolve_timeout",
                job_id=job_id,
                track_id=track_id,
            )
            await session.commit()
            raise HTTPException(
                status_code=504,
                detail="SoundCloud resolve timed out",
            ) from exc
        except HTTPException:
            await session.commit()
            raise
        except Exception as exc:
            log.warning(
                "compute_job_audio_sc_failed",
                job_id=job_id,
                track_id=track_id,
                err=str(exc),
            )
            await session.commit()
            raise HTTPException(status_code=503) from exc
    if not sc_stream_url:
        await session.commit()
        raise HTTPException(status_code=404)

    if proxy and stream_protocol == "progressive" and sc_stream_url:
        if not await cws.consume_ott_by_exp(exp, job.id, worker_id):
            await cws._log_audit(
                session,
                worker_id=worker_id,
                ip=client_ip(request),
                action="ott_fail",
                job_id=job.id,
                status_code=404,
            )
            await session.commit()
            raise HTTPException(status_code=404)
        return StreamingResponse(
            _stream_sc_cdn_to_worker(
                sc_stream_url,
                job_id=job_id,
                chunk_idle_timeout=(settings.lyrics_audio_chunk_idle_seconds),
            ),
            media_type="application/octet-stream",
        )

    if not await cws.consume_ott_by_exp(exp, job.id, worker_id):
        await cws._log_audit(
            session,
            worker_id=worker_id,
            ip=client_ip(request),
            action="ott_fail",
            job_id=job.id,
            status_code=404,
        )
        await session.commit()
        raise HTTPException(status_code=404)
    return JSONResponse(
        status_code=200,
        content={
            "url": sc_stream_url,
            "stream_protocol": stream_protocol,
        },
    )


@router.post("/jobs/{job_id}/progress")
async def job_progress(
    job_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    worker, _ = await verify_worker_hmac_request(
        request,
        session,
    )
    await _enforce_rate_limit(
        request,
        session,
        worker_id=worker.id,
        action="progress",
    )
    j = await crr.get_compute_job_for_worker(
        session,
        job_id,
        worker.id,
    )
    if j is None:
        raise HTTPException(status_code=404)
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=client_ip(request),
        action="compute_progress",
        job_id=job_id,
        status_code=200,
    )
    await session.commit()
    return {"status": "ok"}


@router.post("/jobs/{job_id}/result")
async def job_result(
    job_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    worker, body = await verify_worker_hmac_request(
        request,
        session,
    )
    await _enforce_rate_limit(
        request,
        session,
        worker_id=worker.id,
        action="result",
    )
    j = await crr.get_compute_job_for_worker(
        session,
        job_id,
        worker.id,
    )
    if j is None:
        raise HTTPException(status_code=404)
    if j.status != q.STATUS_CLAIMED:
        raise HTTPException(status_code=409)
    try:
        payload = json.loads(body or b"{}")
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400) from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422)
    error_kind_raw = payload.get("error_kind")
    error_kind = error_kind_raw if isinstance(error_kind_raw, str) else ""
    is_error_result = (
        payload.get("success") is False or payload.get("status") == "error"
    )
    if j.job_type != q.JOB_SOUNDCLOUD_RPC and error_kind and is_error_result:
        outcome = await compute_job_reaper.handle_worker_failure(
            session,
            job=j,
            error_kind=error_kind,
            reason=str(
                payload.get("error") or payload.get("reason") or error_kind
            ),
        )
        await cws._log_audit(
            session,
            worker_id=worker.id,
            ip=client_ip(request),
            action="compute_result_failed",
            job_id=job_id,
            status_code=200,
            meta={"error_kind": error_kind, "outcome": outcome},
        )
        await session.commit()
        return {"status": "ok", "outcome": outcome}
    try:
        await crr.persist_result(
            session,
            job=j,
            result=payload,
        )
    except ValueError as exc:
        await cws._log_audit(
            session,
            worker_id=worker.id,
            ip=client_ip(request),
            action="compute_result_invalid",
            job_id=job_id,
            status_code=422,
            meta={"reason": str(exc)},
        )
        await session.commit()
        raise HTTPException(status_code=422) from exc
    await q.mark_succeeded(
        session,
        job=j,
        result=payload,
    )
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=client_ip(request),
        action="compute_result_ok",
        job_id=job_id,
        status_code=200,
    )
    await session.commit()
    return {"status": "ok"}


@router.post("/jobs/{job_id}/fail")
async def job_fail(
    job_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    worker, body = await verify_worker_hmac_request(
        request,
        session,
    )
    await _enforce_rate_limit(
        request,
        session,
        worker_id=worker.id,
        action="fail",
    )
    j = await crr.get_compute_job_for_worker(
        session,
        job_id,
        worker.id,
    )
    if j is None:
        raise HTTPException(status_code=404)
    if j.status != q.STATUS_CLAIMED:
        raise HTTPException(status_code=409)
    try:
        event = json.loads(body or b"{}")
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400) from exc
    r = event.get("reason")
    reason: str = (
        r
        if isinstance(
            r,
            str,
        )
        and r
        else "job_failed"
    )
    raw_error_kind = event.get("error_kind")
    error_kind = raw_error_kind if isinstance(raw_error_kind, str) else reason
    outcome = await compute_job_reaper.handle_worker_failure(
        session,
        job=j,
        error_kind=error_kind,
        reason=reason,
    )
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=client_ip(request),
        action="compute_fail",
        job_id=job_id,
        status_code=200,
        meta={"reason": reason, "error_kind": error_kind, "outcome": outcome},
    )
    await session.commit()
    return {"status": "ok", "outcome": outcome}


@router.get("/status")
async def compute_status(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    worker, _body = await verify_worker_hmac_request(
        request,
        session,
    )
    await _enforce_rate_limit(
        request,
        session,
        worker_id=worker.id,
        action="status",
    )
    snap = await q.queue_health_snapshot(session)
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=client_ip(request),
        action="compute_status",
        status_code=200,
    )
    await session.commit()
    return snap
