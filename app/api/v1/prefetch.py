"""Prefetch policy endpoint for the Mini App smart-buffering.

Exposes the PrivateCore ``prefetch_policy`` decision functions so
the client can pick its lookahead, storage budget, and warm-segment
sizing per network conditions.
"""

from __future__ import annotations

from dotsound_private_core.services.prefetch_policy import (
    NetworkProfile,
    build_policy_snapshot,
)
from fastapi import APIRouter, Query, Request

from app.core.rate_limit import limiter
from app.schemas.prefetch import PrefetchPolicyResponse

router = APIRouter(prefix="/prefetch", tags=["prefetch"])


def _normalize_effective_type(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    allowed = {"slow-2g", "2g", "3g", "4g"}
    if normalized in allowed:
        return normalized
    return None


@router.get(
    "/policy",
    response_model=PrefetchPolicyResponse,
    summary="Smart-buffering policy snapshot for the Mini App",
)
@limiter.limit("60/minute")
async def get_prefetch_policy(
    request: Request,
    effective_type: str | None = Query(
        None,
        description=(
            "Network Information API effectiveType: "
            "'slow-2g' | '2g' | '3g' | '4g'."
        ),
    ),
    save_data: bool = Query(
        False,
        description="Whether the user enabled Save-Data hint.",
    ),
    downlink: float | None = Query(
        None,
        ge=0.0,
        le=10000.0,
        description="Estimated downlink in Mbit/s.",
    ),
    quota_bytes: int | None = Query(
        None,
        ge=0,
        description=(
            "Storage quota reported by navigator.storage.estimate(). "
            "Used to derive the LRU budget; pass 0 or omit when unknown."
        ),
    ),
) -> PrefetchPolicyResponse:
    profile = NetworkProfile(
        effective_type=_normalize_effective_type(effective_type),
        save_data=bool(save_data),
        downlink_mbps=downlink,
    )
    snapshot = build_policy_snapshot(
        network=profile,
        quota_bytes=quota_bytes if (quota_bytes or 0) > 0 else None,
        enabled=True,
    )
    return PrefetchPolicyResponse(
        enabled=snapshot.enabled,
        algorithm_version=snapshot.algorithm_version,
        hot_pool_size=snapshot.hot_pool_size,
        warm_segments_per_track=snapshot.warm_segments_per_track,
        initial_bytes_per_track=snapshot.initial_bytes_per_track,
        max_storage_bytes=snapshot.max_storage_bytes,
        in_memory_ttl_seconds=snapshot.in_memory_ttl_seconds,
        persistent_ttl_seconds=snapshot.persistent_ttl_seconds,
        eviction_policy=snapshot.eviction_policy,
        concurrent_prefetch_limit=snapshot.concurrent_prefetch_limit,
        skip_third_party_audio_cache=snapshot.skip_third_party_audio_cache,
        lookahead_by_context=dict(snapshot.lookahead_by_context),
    )
