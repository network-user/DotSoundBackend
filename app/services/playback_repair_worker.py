from __future__ import annotations

from typing import Any

import structlog
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.tracks.playback import _resolve_third_party_stream
from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.track import Track
from app.repositories.track import TrackRepository
from app.services.track_fallback_service import TrackFallbackService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _is_soundcloud_track(track: Track) -> bool:
    return track.source_platform == "soundcloud" or bool(track.sc_url)


def _http_detail(exc: HTTPException) -> str:
    detail = exc.detail
    return detail if isinstance(detail, str) else str(detail)


class TrackPlaybackRepairService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def repair_track(self, track_id: int) -> dict[str, Any]:
        track = await self._session.get(Track, track_id)
        if track is None:
            return {
                "track_id": track_id,
                "ok": False,
                "status": "not_found",
                "detail": "Track not found",
            }
        if not track.is_active or track.deleted_at is not None:
            return {
                "track_id": track_id,
                "ok": False,
                "status": "skipped",
                "detail": "Track is inactive",
            }
        if track.access_mode != "third_party_stream":
            return {
                "track_id": track_id,
                "ok": False,
                "status": "skipped",
                "detail": "Track is not a third-party stream",
            }

        before_sc_url = track.sc_url
        refreshed = False
        try:
            protocol = await self._verify_current_source(track)
        except HTTPException as first_exc:
            if not _is_soundcloud_track(track):
                return self._failed_result(track_id, first_exc)
            refreshed = await self._try_refresh_soundcloud_source(track)
            if not refreshed:
                return self._failed_result(track_id, first_exc)
            try:
                protocol = await self._verify_current_source(track)
            except HTTPException as second_exc:
                await self._session.rollback()
                return self._failed_result(track_id, second_exc)
            except Exception as second_exc:  # noqa: BLE001
                await self._session.rollback()
                return self._error_result(track_id, second_exc)
        except Exception as exc:  # noqa: BLE001
            return self._error_result(track_id, exc)

        await self._clear_health(track)
        await self._session.commit()
        new_sc_url = track.sc_url
        logger.info(
            "track_playback_repair_succeeded",
            track_id=track.id,
            refreshed_sc_url=refreshed,
            protocol=protocol,
        )
        return {
            "track_id": track.id,
            "ok": True,
            "status": "repaired",
            "detail": "Playback source resolves",
            "stream_protocol": protocol,
            "refreshed_sc_url": refreshed,
            "sc_url_changed": before_sc_url != new_sc_url,
        }

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

    async def _try_refresh_soundcloud_source(self, track: Track) -> bool:
        fallback = TrackFallbackService(self._session, settings)
        try:
            return await fallback.try_refresh_sc_url(track)
        except Exception:  # noqa: BLE001
            await self._session.rollback()
            logger.exception(
                "track_playback_repair_refresh_failed",
                track_id=track.id,
            )
            return False

    async def _clear_health(self, track: Track) -> None:
        track.playback_suppressed_until = None
        track.playback_last_failure_at = None
        track.playback_last_http_status = None
        track.playback_last_failure_source = None
        track.playback_recovery_failed_at = None
        await self._session.flush()

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
        return {
            "track_id": track_id,
            "ok": False,
            "status": "error",
            "detail": f"{type(exc).__name__}: {exc}",
        }


@broker.task
async def repair_track_playback_task(track_id: int) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        return await TrackPlaybackRepairService(session).repair_track(track_id)


@broker.task
async def sweep_playback_repair_task(
    limit: int | None = None,
) -> dict[str, Any]:
    sweep_limit = int(limit or settings.playback_repair_sweep_limit)
    async with AsyncSessionLocal() as session:
        return await TrackPlaybackRepairService(session).repair_candidates(
            sweep_limit,
        )
