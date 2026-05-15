from __future__ import annotations

from datetime import UTC, datetime

import structlog
from dotsound_private_core.services.playback_health_policy import (
    PLAYBACK_HEALTH_AUTO_SUPPRESS_DURATION,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.track_playback_health import (
    TrackPlaybackHealthRepository,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def is_track_playback_suppressed(track: Track) -> bool:
    until = track.playback_suppressed_until
    if until is None:
        return False
    now = datetime.now(UTC)
    if until.tzinfo is None:
        return until.replace(tzinfo=UTC) > now
    return until > now


def playback_suppressed_blocks_streaming(
    track: Track,
    viewer: object | None,
) -> bool:
    if not is_track_playback_suppressed(track):
        return False
    uid = getattr(viewer, "id", None) if viewer else None
    owner_id = getattr(track, "uploaded_by_id", None)
    return not (uid is not None and owner_id == uid)


class TrackPlaybackHealthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TrackPlaybackHealthRepository(session)

    async def record_server_recovery_exhausted(
        self,
        *,
        track_id: int,
        viewer_user_id: int | None,
        http_status: int,
        detail: str | None,
    ) -> None:
        truncated = detail[:512] if detail else None
        await self._repo.insert_failure_event(
            track_id=track_id,
            user_id=viewer_user_id,
            source="server_recovery_exhausted",
            http_status=http_status,
            detail_truncated=truncated,
        )
        tr = await self._session.get(Track, track_id)
        if tr is None:
            return
        now = datetime.now(UTC)
        tr.playback_last_failure_at = now
        tr.playback_last_http_status = http_status
        tr.playback_last_failure_source = "server_recovery_exhausted"
        tr.playback_recovery_failed_at = now
        await self._session.flush()
        await self._repo.maybe_apply_auto_suppression(track_id=track_id)
        logger.info(
            "playback_health_recovery_exhausted_recorded",
            track_id=track_id,
            http_status=http_status,
        )

    async def record_server_proxy_upstream(
        self,
        *,
        track_id: int,
        viewer_user_id: int | None,
        http_status: int,
        detail: str | None,
    ) -> None:
        truncated = detail[:512] if detail else None
        await self._repo.insert_failure_event(
            track_id=track_id,
            user_id=viewer_user_id,
            source="server_proxy_upstream",
            http_status=http_status,
            detail_truncated=truncated,
        )
        tr = await self._session.get(Track, track_id)
        if tr is None:
            return
        now = datetime.now(UTC)
        tr.playback_last_failure_at = now
        tr.playback_last_http_status = http_status
        tr.playback_last_failure_source = "server_proxy_upstream"
        await self._session.flush()
        await self._repo.maybe_apply_auto_suppression(track_id=track_id)
        logger.info(
            "playback_health_proxy_upstream_recorded",
            track_id=track_id,
            http_status=http_status,
        )

    async def clear_auto_suppression(
        self, track_id: int
    ) -> Track | None:
        tr = await self._session.get(Track, track_id)
        if tr is None:
            return None
        tr.playback_suppressed_until = None
        await self._session.flush()
        return tr

    async def record_import_verification_failed(
        self,
        *,
        track_id: int,
        viewer_user_id: int | None,
        http_status: int | None,
        detail: str | None,
    ) -> None:
        truncated = detail[:512] if detail else None
        await self._repo.insert_failure_event(
            track_id=track_id,
            user_id=viewer_user_id,
            source="import_verification_failed",
            http_status=http_status,
            detail_truncated=truncated,
        )
        tr = await self._session.get(Track, track_id)
        if tr is None:
            return
        now = datetime.now(UTC)
        tr.playback_last_failure_at = now
        tr.playback_last_http_status = http_status
        tr.playback_last_failure_source = "import_verification_failed"
        tr.playback_recovery_failed_at = now
        tr.playback_suppressed_until = (
            now + PLAYBACK_HEALTH_AUTO_SUPPRESS_DURATION
        )
        await self._session.flush()
        logger.info(
            "playback_health_import_verification_failed_recorded",
            track_id=track_id,
            http_status=http_status,
        )

    async def clear_failure_state(self, track_id: int) -> Track | None:
        tr = await self._session.get(Track, track_id)
        if tr is None:
            return None
        tr.playback_suppressed_until = None
        tr.playback_last_failure_at = None
        tr.playback_last_http_status = None
        tr.playback_last_failure_source = None
        tr.playback_recovery_failed_at = None
        await self._session.flush()
        return tr
