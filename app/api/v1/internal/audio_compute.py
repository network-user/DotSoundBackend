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
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import (
    RedirectResponse,
    StreamingResponse,
)

from app.api.v1.internal.worker_request import (
    client_ip,
    verify_worker_hmac_request,
)
from app.config import settings
from app.core import s3
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
from app.services.outbound_proxy import get_outbound_proxy
from app.services.worker_job_control import (
    merge_heartbeat_control_payload,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_SC_PROXY_CHUNK = 64 * 1024
_SC_PROXY_LOG_EVERY_BYTES = 1024 * 1024


def _sc_cdn_proxy_headers() -> dict[str, str]:
    """Browser-like request to ``cf-media.sndcdn.com`` (CloudFront).

    A plain server-side GET often gets 403; these headers and the same
    egress proxy as ``SoundCloudService`` help match how the stream URL
    was minted.
    """
    return {
        "User-Agent": settings.lyrics_sc_cdn_user_agent,
        "Accept": "audio/mpeg, audio/*;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Referer": settings.lyrics_sc_cdn_referer,
        "Origin": "https://soundcloud.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
    }


async def _stream_sc_cdn_to_worker(
    stream_url: str,
    *,
    job_id: str = "",
    chunk_idle_timeout: float = 30.0,
) -> AsyncIterator[bytes]:
    cap = settings.lyrics_max_audio_mb * 1024 * 1024
    n = 0
    last_logged_at_bytes = 0
    sc_host = (
        stream_url.split("://", 1)[-1].split("/", 1)[0]
        if "://" in stream_url
        else "?"
    )
    started = datetime.now(UTC)
    out_proxy = get_outbound_proxy("soundcloud")
    logger.info(
        "audio_compute_sc_proxy_started",
        job_id=job_id,
        sc_host=sc_host,
        outbound_proxied=bool(out_proxy),
    )
    try:
        client_kwargs: dict[str, Any] = {
            "timeout": httpx.Timeout(
                connect=30.0,
                read=chunk_idle_timeout,
                write=30.0,
                pool=30.0,
            ),
            "follow_redirects": True,
            "trust_env": False,
        }
        if out_proxy:
            client_kwargs["proxy"] = out_proxy
        async with (
            httpx.AsyncClient(**client_kwargs) as client,
            client.stream(
                "GET",
                stream_url,
                headers=_sc_cdn_proxy_headers(),
            ) as r,
        ):
            r.raise_for_status()
            iterator = r.aiter_bytes(_SC_PROXY_CHUNK)
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        iterator.__anext__(),
                        timeout=chunk_idle_timeout,
                    )
                except StopAsyncIteration:
                    break
                except TimeoutError:
                    logger.warning(
                        "audio_compute_sc_proxy_chunk_idle",
                        job_id=job_id,
                        bytes_streamed=n,
                        idle_timeout_s=chunk_idle_timeout,
                    )
                    raise
                if not chunk:
                    continue
                n += len(chunk)
                if n > cap:
                    raise ValueError("audio_too_large")
                if n - last_logged_at_bytes >= _SC_PROXY_LOG_EVERY_BYTES:
                    last_logged_at_bytes = n
                    logger.info(
                        "audio_compute_sc_proxy_chunk_progress",
                        job_id=job_id,
                        bytes_streamed=n,
                    )
                yield chunk
        elapsed_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        logger.info(
            "audio_compute_sc_proxy_completed",
            job_id=job_id,
            bytes=n,
            elapsed_ms=elapsed_ms,
        )
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "audio_compute_sc_proxy_http_status",
            job_id=job_id,
            bytes_streamed=n,
            status=exc.response.status_code if exc.response else None,
            sc_host=sc_host,
        )
        raise
    except (
        httpx.HTTPError,
        ValueError,
        TimeoutError,
    ) as exc:
        logger.warning(
            "audio_compute_sc_proxy_failed",
            job_id=job_id,
            bytes_streamed=n,
            err=type(exc).__name__,
        )
        raise


router = APIRouter(
    prefix="/internal/audio-compute",
    tags=["audio-compute"],
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
            audit_ip=client_ip(request),
        )
    except rl.WorkerRateLimitExceeded as exc:
        raise HTTPException(status_code=429) from exc


@router.post("/workers/heartbeat")
async def heartbeat(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    worker, _ = await verify_worker_hmac_request(request, session)
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
    worker, _ = await verify_worker_hmac_request(request, session)
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
            ip=client_ip(request),
            action="claim_empty",
            status_code=204,
        )
        await session.commit()
        # 204 must have no body; ``JSONResponse(..., content=None)``
        # can confuse Content-Length under uvicorn (ASGI).
        return Response(status_code=204)

    token = cws.generate_single_use_token(job.id, worker.id)
    payload = {
        "job_id": job.id,
        "track_id": job.track_id,
        "profile": job.profile,
        "progress_id": job.progress_id,
        "audio_sha256": job.audio_sha256,
        "correlation_id": job.id,
        "current_tier": job.current_tier,
        "deadline_at": (
            job.deadline_at.isoformat() if job.deadline_at else None
        ),
        "audio_url": (
            f"/api/v1/internal/audio-compute/audio/{job.id}" f"?ott={token}"
        ),
    }
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=client_ip(request),
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
    worker, body = await verify_worker_hmac_request(request, session)
    await _enforce_rate_limit(
        request,
        session,
        worker_id=worker.id,
        action="progress",
    )
    try:
        event = json.loads(body or b"{}")
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400) from exc

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
        percent=percent if isinstance(percent, int) else None,
    )

    partial_text = event.get("partial_text")
    if isinstance(partial_text, str) and partial_text:
        await store_partial_text(job.progress_id, partial_text)
    partial_sync = event.get("partial_synced_lines")
    if isinstance(partial_sync, list) and partial_sync:
        await store_partial_synced(job.progress_id, partial_sync)

    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=client_ip(request),
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
    worker, body = await verify_worker_hmac_request(request, session)
    await _enforce_rate_limit(
        request,
        session,
        worker_id=worker.id,
        action="result",
    )
    try:
        payload = json.loads(body or b"{}")
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400) from exc

    repo = AudioComputeRepository(session)
    job = await repo.get_job_for_worker(job_id, worker.id)
    if job is None:
        raise HTTPException(status_code=404)
    if job.status not in {"running", "queued"}:
        raise HTTPException(status_code=409)

    if (
        job.audio_sha256
        and payload.get("audio_sha256")
        and job.audio_sha256 != payload.get("audio_sha256")
    ):
        await cws._log_audit(
            session,
            worker_id=worker.id,
            ip=client_ip(request),
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
            ip=client_ip(request),
            action="result_invalid",
            job_id=job.id,
            status_code=422,
            meta={"reason": str(exc)},
        )
        await session.commit()
        raise HTTPException(status_code=422) from exc

    lyrics_repo = LyricsRepository(session)
    existing = await lyrics_repo.get_by_track_id(job.track_id)

    plain_out = clean["plain_text"]
    synced_out = clean["synced_lines"]
    sq_out = clean["sync_quality"]
    sp_out = clean["sync_profile"]
    sn_out: str | None
    ssn_out: str | None

    use_catalog = (
        existing is not None
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
                (float(x["t"]), str(x["w"])) for x in tw_list
            ]

            def _align() -> list[SyncedLine] | None:
                audio_seconds = float(clean.get("audio_seconds") or 0.0)
                audio_duration_ms = (
                    int(audio_seconds * 1000) if audio_seconds > 0.0 else 0
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
                "confidence": float(getattr(sl, "confidence", 0.0) or 0.0),
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
            started_aware = started_aware.replace(tzinfo=UTC)
        duration_ms = int(
            (datetime.now(UTC) - started_aware).total_seconds() * 1000
        )
    await cws.mark_job_result(session, job=job, duration_ms=duration_ms)

    audio_seconds = float(payload.get("audio_seconds") or 0)
    try:
        from app.services.compute_anomaly_service import (
            record_remote_result,
        )

        await record_remote_result(
            session,
            worker_id=worker.id,
            job_id=job.id,
            audio_seconds=audio_seconds,
            processing_seconds=(duration_ms / 1000.0),
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
        ip=client_ip(request),
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
    worker, body = await verify_worker_hmac_request(request, session)
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

    logger.warning(
        "audio_compute_worker_fail",
        job_id=job_id,
        worker_id=worker.id,
        reason=reason[:512],
    )
    try:
        from app.services.lyrics_cascade import (
            handle_tier_failure,
        )

        will_fallback = await handle_tier_failure(
            session,
            job=job,
            reason=reason,
            with_sync=bool(getattr(job, "request_with_sync", False)),
            bypass_cache=bool(
                getattr(
                    job,
                    "request_bypass_cache",
                    False,
                )
            ),
        )
    except ImportError:
        will_fallback = False

    if not will_fallback:
        await cws.mark_job_failed(session, job=job, reason=reason)
        await set_lyrics_progress(
            job.progress_id,
            stage="error",
            terminal_state="error",
            log_line=f"remote worker failed: {reason}",
        )
    await cws._log_audit(
        session,
        worker_id=worker.id,
        ip=client_ip(request),
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

    repo = AudioComputeRepository(session)
    job = await repo.get_job_for_worker(job_id, worker_id)
    if job is None or job.status != "running":
        raise HTTPException(status_code=404)

    expected_ip = job.routed_to_worker and (
        await repo.get_worker(job.routed_to_worker)
    )
    pinned_ip = expected_ip.last_ip if expected_ip else None
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

    file_key = await repo.get_track_file_key(job.track_id)
    logger.info(
        "audio_compute_audio_request_start",
        job_id=job_id,
        track_id=job.track_id,
        proxy=proxy,
        has_file_key=bool(file_key),
    )
    payload: dict
    s3_presigned: str | None = None
    sc_url_pair: tuple[str, str] | None = None
    if file_key:
        try:
            presigned = await s3.get_presigned_url(file_key)
        except Exception as exc:
            logger.warning(
                "audio_presign_failed",
                job_id=job_id,
                track_id=job.track_id,
                err=str(exc),
            )
            await session.commit()
            raise HTTPException(status_code=503) from exc
        s3_presigned = presigned
        payload = {"url": presigned}
        logger.info(
            "audio_compute_audio_resolved",
            job_id=job_id,
            track_id=job.track_id,
            source="s3",
        )
    else:
        track = await session.get(Track, job.track_id)
        if not track or not getattr(track, "sc_url", None):
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

        sc = SoundCloudService(settings.sc_client_id, session)
        try:
            sc_stream_url, protocol = await asyncio.wait_for(
                sc.get_stream_info(
                    track.sc_url,
                    use_cache=False,
                ),
                timeout=(settings.lyrics_audio_resolve_timeout_seconds),
            )
        except TimeoutError as exc:
            logger.warning(
                "audio_compute_sc_resolve_timeout",
                job_id=job_id,
                track_id=job.track_id,
                timeout_s=(settings.lyrics_audio_resolve_timeout_seconds),
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
            logger.warning(
                "audio_download_sc_failed",
                job_id=job_id,
                track_id=job.track_id,
                err=str(exc),
            )
            await session.commit()
            raise HTTPException(status_code=503) from exc
        sc_url_pair = (sc_stream_url, protocol)
        payload = {
            "url": sc_stream_url,
            "stream_protocol": protocol,
        }
        logger.info(
            "audio_compute_audio_resolved",
            job_id=job_id,
            track_id=job.track_id,
            source="sc",
            protocol=protocol,
        )

    if proxy and s3_presigned is not None:
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
        logger.info(
            "audio_compute_audio_response_dispatched",
            job_id=job_id,
            response="s3_redirect",
        )
        return RedirectResponse(
            url=s3_presigned,
            status_code=302,
        )

    if proxy and sc_url_pair is not None and sc_url_pair[1] == "progressive":
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
        logger.info(
            "audio_compute_audio_response_dispatched",
            job_id=job_id,
            response="sc_proxy_stream",
        )
        return StreamingResponse(
            _stream_sc_cdn_to_worker(
                sc_url_pair[0],
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

    logger.info(
        "audio_compute_audio_response_dispatched",
        job_id=job_id,
        response="json_url",
    )
    return JSONResponse(
        status_code=200,
        content=payload,
    )
