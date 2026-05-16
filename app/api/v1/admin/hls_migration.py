"""Admin HLS bundle migration endpoints.

Operator-facing controls for the worker that re-transcodes legacy
10s-segment HLS bundles to the current 4s layout. Status surfaces
how much catalogue is still on the old version; trigger schedules
a single batch and returns immediately so the admin UI does not
hang on long-running ffmpeg work.
"""

from __future__ import annotations

import structlog
from dotsound_private_core.services.playback_streaming_policy import (
    HLS_MIGRATE_BATCH_SIZE,
    LATEST_BUNDLE_VERSION,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.dependencies import require_capability
from app.models.user import User
from app.services.hls_migration_worker import (
    count_outdated_tracks,
    enqueue_migration_batch,
)

router = APIRouter(prefix="/hls-migration", tags=["admin-hls-migration"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class HlsMigrationStatusResponse(BaseModel):
    """Catalogue snapshot for the admin migration UI."""

    target_bundle_version: int
    outdated_tracks: int


class HlsMigrationTriggerResponse(BaseModel):
    scheduled: int = Field(ge=0)


@router.get(
    "/status",
    response_model=HlsMigrationStatusResponse,
    summary="Count tracks still on the legacy HLS bundle layout",
)
async def hls_migration_status(
    _admin: User = Depends(require_capability("tracks.manage")),
) -> HlsMigrationStatusResponse:
    return HlsMigrationStatusResponse(
        target_bundle_version=LATEST_BUNDLE_VERSION,
        outdated_tracks=await count_outdated_tracks(),
    )


@router.post(
    "/trigger",
    response_model=HlsMigrationTriggerResponse,
    summary="Enqueue a migration batch (rate-limited inside)",
)
async def hls_migration_trigger(
    limit: int = Query(
        HLS_MIGRATE_BATCH_SIZE,
        ge=1,
        le=HLS_MIGRATE_BATCH_SIZE * 16,
        description="Maximum tasks to enqueue in this batch",
    ),
    _admin: User = Depends(require_capability("tracks.manage")),
) -> HlsMigrationTriggerResponse:
    try:
        scheduled = await enqueue_migration_batch(limit=limit)
    except Exception as exc:
        logger.exception("hls_migration_trigger_failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue HLS migration batch",
        ) from exc
    return HlsMigrationTriggerResponse(scheduled=scheduled)
