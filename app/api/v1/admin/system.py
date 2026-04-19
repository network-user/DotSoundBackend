"""Admin system endpoints (services, migrations, feature flags, containers)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import (
    get_db,
    require_capability,
    require_step_up,
)
from app.models.user import User
from app.repositories.app_settings import (
    FEATURE_FLAG_PREFIX,
    AppSettingsRepository,
)
from app.services.admin_manifest_service import (
    KNOWN_CAPABILITIES,
)
from app.services.backup_service import (
    ALLOWED_KINDS,
    enqueue_backup,
    list_backups,
)
from app.services.container_health_service import (
    get_container_summary,
)

_AI_TRACK_INFO_TTL_KEY = "ai.track_info_ttl_days"
_AI_ARTIST_SUPPLEMENTAL_TTL_KEY = "ai.artist_supplemental_ttl_days"


class AiSettingsResponse(BaseModel):
    track_info_ttl_days: int
    artist_supplemental_ttl_days: int


class AiSettingsUpdate(BaseModel):
    track_info_ttl_days: int | None = None
    artist_supplemental_ttl_days: int | None = None

router = APIRouter(prefix="/system", tags=["admin-system"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.get("/services")
async def services_health(
    _admin: User = Depends(require_capability("metrics.view")),
) -> dict[str, Any]:
    from app.api.v1.health import health_deep

    response = await health_deep()
    return response.model_dump()


@router.get("/containers")
async def containers(
    _admin: User = Depends(require_capability("containers.view")),
) -> dict[str, Any]:
    return await get_container_summary()


@router.get("/migrations")
async def migrations(
    _admin: User = Depends(require_capability("settings.manage")),
) -> dict[str, Any]:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="alembic not available",
        ) from exc
    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    revisions = []
    for rev in script.walk_revisions():
        revisions.append(
            {
                "revision": rev.revision,
                "down_revision": rev.down_revision,
                "doc": (rev.doc or "").strip(),
            }
        )
    head = script.get_current_head()
    return {
        "head": head,
        "revisions": revisions,
    }


@router.get("/feature-flags")
async def list_feature_flags(
    _admin: User = Depends(require_capability("feature_flags.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repo = AppSettingsRepository(session)
    rows = await repo.list_feature_flags()
    return {
        "items": [
            {
                "key": row.key.removeprefix(FEATURE_FLAG_PREFIX),
                "value": row.value,
                "updated_by": row.updated_by,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]
    }


@router.patch("/feature-flags/{name}")
async def set_feature_flag(
    name: str,
    enabled: bool = Body(..., embed=True),
    admin: User = Depends(require_step_up("system.feature_flags.set")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repo = AppSettingsRepository(session)
    row = await repo.set_feature_flag(name, enabled, updated_by=admin.id)
    return {
        "key": row.key.removeprefix(FEATURE_FLAG_PREFIX),
        "value": row.value,
    }


@router.get("/known-capabilities")
async def known_capabilities(
    _admin: User = Depends(require_capability("settings.manage")),
) -> dict[str, Any]:
    return {"capabilities": sorted(KNOWN_CAPABILITIES)}


@router.get("/backups")
async def backups(
    _admin: User = Depends(require_capability("backups.view")),
) -> dict[str, Any]:
    return await list_backups()


@router.post("/backups/run")
async def run_backup(
    kind: str = Body(
        "full",
        embed=True,
        min_length=2,
        max_length=16,
    ),
    _admin: User = Depends(require_step_up("system.backups.run")),
) -> dict[str, Any]:
    if kind not in ALLOWED_KINDS:
        raise HTTPException(
            status_code=400,
            detail="unknown backup kind",
        )
    try:
        result = await enqueue_backup(kind=kind)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    logger.info(
        "admin_backup_run_requested",
        kind=kind,
        task_id=result.get("task_id"),
    )
    return {"queued": True, **result}


@router.get("/ai-settings", response_model=AiSettingsResponse)
async def get_ai_settings(
    _admin: User = Depends(require_capability("settings.manage")),
    session: AsyncSession = Depends(get_db),
) -> AiSettingsResponse:
    repo = AppSettingsRepository(session)

    track_val = await repo.get_value(_AI_TRACK_INFO_TTL_KEY)
    artist_val = await repo.get_value(_AI_ARTIST_SUPPLEMENTAL_TTL_KEY)

    def _extract_days(val: Any, default: int) -> int:
        if isinstance(val, dict) and "days" in val:
            try:
                days = int(val["days"])
                if days > 0:
                    return days
            except (TypeError, ValueError):
                pass
        return default

    return AiSettingsResponse(
        track_info_ttl_days=_extract_days(
            track_val, settings.track_info_ttl_days
        ),
        artist_supplemental_ttl_days=_extract_days(
            artist_val, settings.artist_supplemental_ttl_days
        ),
    )


@router.put("/ai-settings", response_model=AiSettingsResponse)
async def update_ai_settings(
    body: AiSettingsUpdate,
    admin: User = Depends(require_capability("settings.manage")),
    session: AsyncSession = Depends(get_db),
) -> AiSettingsResponse:
    repo = AppSettingsRepository(session)

    if body.track_info_ttl_days is not None:
        if body.track_info_ttl_days < 1:
            raise HTTPException(
                status_code=400, detail="track_info_ttl_days must be >= 1"
            )
        await repo.upsert(
            key=_AI_TRACK_INFO_TTL_KEY,
            value={"days": body.track_info_ttl_days},
            updated_by=admin.id,
        )

    if body.artist_supplemental_ttl_days is not None:
        if body.artist_supplemental_ttl_days < 1:
            raise HTTPException(
                status_code=400,
                detail="artist_supplemental_ttl_days must be >= 1",
            )
        await repo.upsert(
            key=_AI_ARTIST_SUPPLEMENTAL_TTL_KEY,
            value={"days": body.artist_supplemental_ttl_days},
            updated_by=admin.id,
        )

    await session.commit()
    return await get_ai_settings(_admin=admin, session=session)
