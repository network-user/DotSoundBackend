from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.tracks.playback import _resolve_third_party_stream
from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.background_job import BackgroundJob
from app.models.track import Track
from app.repositories.track import TrackRepository
from app.services import playback_repair_progress as progress
from app.services.cancellation import is_cancelled
from app.services.track_fallback_service import TrackFallbackService
from app.services.track_playback_health_service import (
    TrackPlaybackHealthService,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _is_soundcloud_track(track: Track) -> bool:
    source_platform = (track.source_platform or "").strip().lower()
    return source_platform == "soundcloud" or bool(track.sc_url)


def _http_detail(exc: HTTPException) -> str:
    detail = exc.detail
    return detail if isinstance(detail, str) else str(detail)


class TrackPlaybackRepairService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def repair_track(
        self,
        track_id: int,
        progress_id: str | None = None,
        background_job_id: str | None = None,
        bypass_refresh_cache: bool = False,
    ) -> dict[str, Any]:
        cancelled = await self._cancel_if_requested(
            track_id,
            progress_id,
            background_job_id,
        )
        if cancelled is not None:
            return cancelled
        await progress.safe_set_progress(
            progress_id,
            stage="loading_track",
            track_id=track_id,
            log_line="loading track",
        )
        track = await self._session.get(Track, track_id)
        if track is None:
            result = {
                "track_id": track_id,
                "ok": False,
                "status": "not_found",
                "detail": "Track not found",
            }
            await progress.safe_set_progress(
                progress_id,
                stage="not_found",
                track_id=track_id,
                log_line="track not found",
                result=result,
            )
            return result
        if not track.is_active or track.deleted_at is not None:
            result = {
                "track_id": track_id,
                "ok": False,
                "status": "skipped",
                "detail": "Track is inactive",
            }
            await progress.safe_set_progress(
                progress_id,
                stage="skipped",
                track_id=track_id,
                log_line="track is inactive",
                result=result,
            )
            return result
        if track.access_mode != "third_party_stream":
            result = {
                "track_id": track_id,
                "ok": False,
                "status": "skipped",
                "detail": "Track is not a third-party stream",
            }
            await progress.safe_set_progress(
                progress_id,
                stage="skipped",
                track_id=track_id,
                log_line="track is not a third-party stream",
                result=result,
            )
            return result

        cancelled = await self._cancel_if_requested(
            track_id,
            progress_id,
            background_job_id,
        )
        if cancelled is not None:
            return cancelled
        before_sc_url = track.sc_url
        refreshed = False
        repair_attempted = False
        try:
            await progress.safe_set_progress(
                progress_id,
                stage="verifying_current_source",
                track_id=track_id,
                log_line="verifying current source",
            )
            protocol = await self._verify_current_source(track)
        except HTTPException as first_exc:
            cancelled = await self._cancel_if_requested(
                track_id,
                progress_id,
                background_job_id,
            )
            if cancelled is not None:
                return cancelled
            if not _is_soundcloud_track(track):
                result = self._failed_result(track_id, first_exc)
                await progress.safe_set_progress(
                    progress_id,
                    stage="unresolved",
                    track_id=track_id,
                    log_line="current source did not resolve",
                    result=result,
                )
                return result
            repair_attempted = True
            cancelled = await self._cancel_if_requested(
                track_id,
                progress_id,
                background_job_id,
            )
            if cancelled is not None:
                return cancelled
            await progress.safe_set_progress(
                progress_id,
                stage="refreshing_source",
                track_id=track_id,
                log_line="trying source refresh",
            )
            try:
                refreshed = await self._try_refresh_soundcloud_source(
                    track,
                    bypass_refresh_cache=bypass_refresh_cache,
                )
            except Exception as refresh_exc:  # noqa: BLE001
                await self._session.rollback()
                result = self._error_result(track_id, refresh_exc)
                await progress.safe_set_progress(
                    progress_id,
                    stage="error",
                    track_id=track_id,
                    log_line="source refresh failed",
                    result=result,
                )
                return result
            cancelled = await self._cancel_if_requested(
                track_id,
                progress_id,
                background_job_id,
            )
            if cancelled is not None:
                return cancelled
            if not refreshed:
                result = await self._record_unresolved(
                    track_id,
                    first_exc,
                )
                await progress.safe_set_progress(
                    progress_id,
                    stage="unresolved",
                    track_id=track_id,
                    log_line=(
                        "source refresh did not find a replacement; "
                        "track suppressed"
                    ),
                    result=result,
                )
                return result
            try:
                await progress.safe_set_progress(
                    progress_id,
                    stage="verifying_refreshed_source",
                    track_id=track_id,
                    log_line="verifying refreshed source",
                )
                protocol = await self._verify_current_source(track)
            except HTTPException as second_exc:
                await self._session.rollback()
                cancelled = await self._cancel_if_requested(
                    track_id,
                    progress_id,
                    background_job_id,
                )
                if cancelled is not None:
                    return cancelled
                result = await self._record_unresolved(
                    track_id,
                    second_exc,
                )
                await progress.safe_set_progress(
                    progress_id,
                    stage="unresolved",
                    track_id=track_id,
                    log_line=(
                        "refreshed source did not resolve; "
                        "track suppressed"
                    ),
                    result=result,
                )
                return result
            except Exception as second_exc:  # noqa: BLE001
                await self._session.rollback()
                cancelled = await self._cancel_if_requested(
                    track_id,
                    progress_id,
                    background_job_id,
                )
                if cancelled is not None:
                    return cancelled
                result = self._error_result(track_id, second_exc)
                await progress.safe_set_progress(
                    progress_id,
                    stage="error",
                    track_id=track_id,
                    log_line="repair failed with unexpected error",
                    result=result,
                )
                return result
        except Exception as exc:  # noqa: BLE001
            result = self._error_result(track_id, exc)
            await progress.safe_set_progress(
                progress_id,
                stage="error",
                track_id=track_id,
                log_line="repair failed with unexpected error",
                result=result,
            )
            return result

        cancelled = await self._cancel_if_requested(
            track_id,
            progress_id,
            background_job_id,
        )
        if cancelled is not None:
            return cancelled
        await progress.safe_set_progress(
            progress_id,
            stage="clearing_health",
            track_id=track_id,
            log_line="clearing playback health marks",
        )
        await self._clear_health(
            track,
            repair_attempted=repair_attempted,
        )
        cancelled = await self._cancel_if_requested(
            track_id,
            progress_id,
            background_job_id,
        )
        if cancelled is not None:
            return cancelled
        await self._session.commit()
        new_sc_url = track.sc_url
        logger.info(
            "track_playback_repair_succeeded",
            track_id=track.id,
            refreshed_sc_url=refreshed,
            protocol=protocol,
        )
        result = {
            "track_id": track.id,
            "ok": True,
            "status": "repaired",
            "detail": "Playback source resolves",
            "stream_protocol": protocol,
            "refreshed_sc_url": refreshed,
            "sc_url_changed": before_sc_url != new_sc_url,
        }
        await progress.safe_set_progress(
            progress_id,
            stage="repaired",
            track_id=track_id,
            log_line="playback repair completed",
            result=result,
        )
        return result

    async def repair_candidates(self, limit: int) -> dict[str, Any]:
        repo = TrackRepository(self._session)
        rows = await repo.list_soundcloud_playback_repair_candidates(
            limit=limit,
        )
        track_ids = [row.id for row in rows]
        results: list[dict[str, Any]] = []
        for track_id in track_ids:
            results.append(await self.repair_track(track_id))
        repaired = sum(1 for item in results if item.get("ok") is True)
        return {
            "inspected": len(track_ids),
            "repaired": repaired,
            "results": results,
        }

    async def _verify_current_source(self, track: Track) -> str:
        _url, protocol = await _resolve_third_party_stream(
            track,
            self._session,
            use_cache=False,
        )
        return protocol

    async def _try_refresh_soundcloud_source(
        self,
        track: Track,
        *,
        bypass_refresh_cache: bool,
    ) -> bool:
        track_id = track.id
        fallback = TrackFallbackService(self._session, settings)
        try:
            return await fallback.try_refresh_sc_url(
                track,
                use_no_match_cache=not bypass_refresh_cache,
            )
        except Exception:  # noqa: BLE001
            await self._session.rollback()
            logger.exception(
                "track_playback_repair_refresh_failed",
                track_id=track_id,
            )
            raise

    async def _clear_health(
        self,
        track: Track,
        *,
        repair_attempted: bool,
    ) -> None:
        now = datetime.now(UTC)
        track.playback_last_checked_at = now
        if repair_attempted:
            track.playback_last_repair_attempt_at = now
        track.playback_suppressed_until = None
        track.playback_last_failure_at = None
        track.playback_last_http_status = None
        track.playback_last_failure_source = None
        track.playback_recovery_failed_at = None
        await self._session.flush()

    async def _cancel_if_requested(
        self,
        track_id: int,
        progress_id: str | None,
        background_job_id: str | None,
    ) -> dict[str, Any] | None:
        if not background_job_id:
            return None
        if not await self._is_cancel_requested(background_job_id):
            return None
        await self._session.rollback()
        result = {
            "track_id": track_id,
            "ok": False,
            "status": "cancelled",
            "detail": "Playback repair cancelled",
            "background_job_id": background_job_id,
        }
        await progress.safe_set_progress(
            progress_id,
            stage="cancelled",
            track_id=track_id,
            log_line="playback repair cancelled",
            result=result,
        )
        logger.info(
            "track_playback_repair_cancelled",
            track_id=track_id,
            background_job_id=background_job_id,
        )
        return result

    async def _is_cancel_requested(self, background_job_id: str) -> bool:
        if await is_cancelled(background_job_id):
            return True
        row = await self._session.get(
            BackgroundJob,
            background_job_id,
            populate_existing=True,
        )
        return row is not None and row.status in {
            "cancelled",
            "cancelling",
        }

    async def _record_unresolved(
        self,
        track_id: int,
        exc: HTTPException,
    ) -> dict[str, Any]:
        result = self._failed_result(track_id, exc)
        await TrackPlaybackHealthService(
            self._session,
        ).record_scheduled_audit_failed(
            track_id=track_id,
            http_status=exc.status_code,
            detail=_http_detail(exc),
        )
        await self._session.commit()
        result["suppressed"] = True
        return result

    @staticmethod
    def _failed_result(
        track_id: int,
        exc: HTTPException,
    ) -> dict[str, Any]:
        return {
            "track_id": track_id,
            "ok": False,
            "status": "unresolved",
            "detail": _http_detail(exc),
            "http_status": exc.status_code,
        }

    @staticmethod
    def _error_result(track_id: int, exc: BaseException) -> dict[str, Any]:
        if isinstance(exc, HTTPException):
            return {
                "track_id": track_id,
                "ok": False,
                "status": "error",
                "detail": _http_detail(exc),
                "http_status": exc.status_code,
            }
        return {
            "track_id": track_id,
            "ok": False,
            "status": "error",
            "detail": f"{type(exc).__name__}: {exc}",
        }


@broker.task
async def repair_track_playback_task(
    track_id: int,
    progress_id: str = "",
    background_job_id: str = "",
    bypass_refresh_cache: bool = False,
) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        return await TrackPlaybackRepairService(session).repair_track(
            track_id,
            progress_id=progress_id or None,
            background_job_id=background_job_id or None,
            bypass_refresh_cache=bypass_refresh_cache,
        )


@broker.task
async def sweep_playback_repair_task(
    limit: int | None = None,
) -> dict[str, Any]:
    sweep_limit = int(limit or settings.playback_repair_sweep_limit)
    async with AsyncSessionLocal() as session:
        return await TrackPlaybackRepairService(session).repair_candidates(
            sweep_limit,
        )
