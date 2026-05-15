"""Admin system endpoints (services, migrations, feature flags, containers)."""

from __future__ import annotations

from typing import Any

import structlog
from dotsound_private_core.services.recommendation_engine import (
    RadioTuning,
    normalize_radio_tuning,
)
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
_RADIO_TUNING_KEY = "recsys.radio_tuning"


class AiSettingsResponse(BaseModel):
    track_info_ttl_days: int
    artist_supplemental_ttl_days: int


class AiSettingsUpdate(BaseModel):
    track_info_ttl_days: int | None = None
    artist_supplemental_ttl_days: int | None = None


class RadioTuningPayload(BaseModel):
    recent_track_cooldown_hours: float = 3.0
    soft_recent_days: float = 2.0
    rediscovery_days: float = 21.0
    artist_cooldown_window: int = 2
    seed_lock_min: int = 2
    seed_lock_max: int = 5
    unseen_boost: float = 0.28
    favorite_boost_cap: float = 0.2
    explicit_like_boost: float = 0.22
    rediscovery_boost: float = 0.2
    similar_recent_penalty: float = 0.2
    queue_pool_multiplier: int = 8


class RadioTuningResponse(BaseModel):
    enabled: bool
    ab_split_percent_b: int
    variant_a: RadioTuningPayload
    variant_b: RadioTuningPayload


class RadioTuningUpdate(BaseModel):
    enabled: bool | None = None
    ab_split_percent_b: int | None = None
    variant_a: RadioTuningPayload | None = None
    variant_b: RadioTuningPayload | None = None


router = APIRouter(prefix="/system", tags=["admin-system"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.get("/services")
async def services_health(
    _admin: User = Depends(require_capability("metrics.view")),
) -> dict[str, Any]:
    from app.api.v1.health import health_deep

    response = await health_deep()
    return response.model_dump()


@router.get("/outbound-status")
async def outbound_status(
    _admin: User = Depends(require_capability("metrics.view")),
) -> dict[str, Any]:
    """Live snapshot of the internal outbound HTTP layer.

    The shape is intentionally opaque: the response describes *what*
    the layer is doing (mode, identity counts, per-service traffic,
    breaker states) without naming any specific implementation. Used
    by the admin dashboard to render an at-a-glance anti-ban posture.
    """
    try:
        from dotsound_private_core.services.outbound import (
            outbound_status as _privatecore_outbound_status,
        )
    except ImportError:
        return {"available": False}
    try:
        snapshot = await _privatecore_outbound_status()
    except Exception as exc:
        logger.warning(
            "admin_outbound_status_unavailable",
            error=type(exc).__name__,
        )
        return {
            "available": False,
            "error": type(exc).__name__,
        }
    return {"available": True, **snapshot}


@router.get("/observability")
async def observability_status(
    _admin: User = Depends(require_capability("metrics.view")),
) -> dict[str, Any]:
    """Report availability of observability backends (Loki / Prometheus)."""
    import httpx

    result: dict[str, Any] = {
        "loki": {"configured": bool(settings.loki_url), "reachable": False},
        "prometheus": {
            "configured": bool(settings.prometheus_url),
            "reachable": False,
        },
    }
    if settings.loki_url:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    settings.loki_url.rstrip("/") + "/ready"
                )
                result["loki"]["reachable"] = resp.status_code < 500
        except Exception:
            result["loki"]["reachable"] = False
    if settings.prometheus_url:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    settings.prometheus_url.rstrip("/") + "/-/ready"
                )
                result["prometheus"]["reachable"] = resp.status_code < 500
        except Exception:
            result["prometheus"]["reachable"] = False
    return result


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

    def _extract_days(val: object, default: int) -> int:
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


def _to_payload(tuning: RadioTuning) -> RadioTuningPayload:
    return RadioTuningPayload(
        recent_track_cooldown_hours=tuning.recent_track_cooldown_hours,
        soft_recent_days=tuning.soft_recent_days,
        rediscovery_days=tuning.rediscovery_days,
        artist_cooldown_window=tuning.artist_cooldown_window,
        seed_lock_min=tuning.seed_lock_min,
        seed_lock_max=tuning.seed_lock_max,
        unseen_boost=tuning.unseen_boost,
        favorite_boost_cap=tuning.favorite_boost_cap,
        explicit_like_boost=tuning.explicit_like_boost,
        rediscovery_boost=tuning.rediscovery_boost,
        similar_recent_penalty=tuning.similar_recent_penalty,
        queue_pool_multiplier=tuning.queue_pool_multiplier,
    )


@router.get("/radio-tuning", response_model=RadioTuningResponse)
async def get_radio_tuning(
    _admin: User = Depends(require_capability("settings.manage")),
    session: AsyncSession = Depends(get_db),
) -> RadioTuningResponse:
    repo = AppSettingsRepository(session)
    raw = await repo.get_value(_RADIO_TUNING_KEY, default={})
    if not isinstance(raw, dict):
        raw = {}
    base = normalize_radio_tuning(None)
    variant_a = normalize_radio_tuning(raw.get("variant_a"))
    variant_b = normalize_radio_tuning(raw.get("variant_b"))
    return RadioTuningResponse(
        enabled=bool(raw.get("enabled", False)),
        ab_split_percent_b=max(
            0,
            min(100, int(raw.get("ab_split_percent_b", 50))),
        ),
        variant_a=_to_payload(variant_a or base),
        variant_b=_to_payload(variant_b or base),
    )


@router.put("/radio-tuning", response_model=RadioTuningResponse)
async def update_radio_tuning(
    body: RadioTuningUpdate,
    admin: User = Depends(require_capability("settings.manage")),
    session: AsyncSession = Depends(get_db),
) -> RadioTuningResponse:
    repo = AppSettingsRepository(session)
    current = await repo.get_value(_RADIO_TUNING_KEY, default={})
    if not isinstance(current, dict):
        current = {}

    enabled = (
        bool(body.enabled)
        if body.enabled is not None
        else bool(current.get("enabled", False))
    )
    split = (
        body.ab_split_percent_b
        if body.ab_split_percent_b is not None
        else int(current.get("ab_split_percent_b", 50))
    )
    split = max(0, min(100, int(split)))

    cur_a = normalize_radio_tuning(current.get("variant_a"))
    cur_b = normalize_radio_tuning(current.get("variant_b"))
    var_a = (
        normalize_radio_tuning(body.variant_a.model_dump())
        if body.variant_a is not None
        else cur_a
    )
    var_b = (
        normalize_radio_tuning(body.variant_b.model_dump())
        if body.variant_b is not None
        else cur_b
    )
    payload = {
        "enabled": enabled,
        "ab_split_percent_b": split,
        "variant_a": _to_payload(var_a).model_dump(),
        "variant_b": _to_payload(var_b).model_dump(),
    }
    await repo.upsert(
        key=_RADIO_TUNING_KEY,
        value=payload,
        updated_by=admin.id,
    )
    await session.commit()
    return await get_radio_tuning(_admin=admin, session=session)
