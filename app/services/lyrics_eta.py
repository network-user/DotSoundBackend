"""Rolling stats and ETA estimate for lyrics generation.

Keeps a small circular buffer of recent stage durations per
profile, then quickly estimates how long a new run is going to
take. All math lives in Backend (transport) — PrivateCore is not
consulted, so labels stay opaque.
"""

from __future__ import annotations

import json
from statistics import median

from app.config import settings
from app.core.redis import get_redis_client

STATS_PREFIX = "lyrics:stats:"
_MAX_SAMPLES = 100

DEFAULT_STAGES: tuple[str, ...] = (
    "searching",
    "downloading_audio",
    "processing",
    "saving",
)


def _stats_key(profile: str, stage: str) -> str:
    return f"{STATS_PREFIX}{profile}:{stage}"


async def record_stage_duration(
    profile: str, stage: str, duration_ms: int
) -> None:
    if duration_ms <= 0:
        return
    redis = get_redis_client()
    key = _stats_key(profile, stage)
    await redis.lpush(key, str(int(duration_ms)))
    await redis.ltrim(key, 0, _MAX_SAMPLES - 1)
    await redis.expire(
        key, int(settings.lyrics_search_cache_ttl_seconds)
    )


async def _stage_p50(profile: str, stage: str) -> int | None:
    redis = get_redis_client()
    raw = await redis.lrange(_stats_key(profile, stage), 0, -1)
    if not raw:
        return None
    values: list[int] = []
    for v in raw:
        try:
            values.append(int(v))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return int(median(values))


async def estimate_total_ms(
    profile: str,
    stages: tuple[str, ...] | None = None,
) -> dict:
    """Return estimated durations per stage and overall total.

    Missing samples fall back to a conservative guess per stage.
    """
    if stages is None:
        stages = DEFAULT_STAGES
    fallback = {
        "searching": 8_000,
        "downloading_audio": 10_000,
        "processing": 180_000,
        "saving": 1_000,
    }
    per_stage: dict[str, int] = {}
    for stage in stages:
        observed = await _stage_p50(profile, stage)
        per_stage[stage] = observed or fallback.get(stage, 2_000)
    total = sum(per_stage.values())
    return {"per_stage": per_stage, "total_ms": total}


async def initial_eta_payload(profile: str) -> dict:
    est = await estimate_total_ms(profile)
    return {"eta_ms": est["total_ms"], "stages": est["per_stage"]}


async def publish_initial_eta(
    progress_id: str, profile: str
) -> int:
    """Seed the progress snapshot with an ETA hint.

    Returns the estimated total duration so caller may log it.
    """
    import json as _json

    redis = get_redis_client()
    key = f"lyrics:progress:{progress_id}"
    raw = await redis.get(key)
    data: dict = {}
    if raw:
        try:
            data = _json.loads(raw)
        except (TypeError, ValueError):
            data = {}
    est = await initial_eta_payload(profile)
    data.setdefault("stage", "queued")
    data.setdefault("logs", [])
    data["eta_ms"] = est["eta_ms"]
    data["stages_eta"] = est["stages"]
    await redis.set(
        key,
        _json.dumps(data, ensure_ascii=False),
        ex=int(settings.lyrics_progress_ttl_seconds),
    )
    await redis.publish(
        f"lyrics:events:{progress_id}",
        json.dumps(
            {
                "type": "eta",
                "eta_ms": est["eta_ms"],
                "stages": est["stages"],
            },
            ensure_ascii=False,
        ),
    )
    return int(est["eta_ms"])
