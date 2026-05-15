from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TypedDict

import structlog

from app.core.redis import get_redis_client

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_KEY_PREFIX = "admin:radio_auto_skip_reasons:"
_TTL_SECONDS = 35 * 24 * 60 * 60
_UNKNOWN = "unknown"


class RadioAutoSkipReasonStat(TypedDict):
    error_code: str
    error_reason: str
    count: int


def _clean(value: object, *, max_len: int) -> str:
    if not isinstance(value, str):
        return _UNKNOWN
    text = " ".join(value.strip().split())
    if not text:
        return _UNKNOWN
    return text[:max_len]


def _day_key(day: datetime) -> str:
    return f"{_KEY_PREFIX}{day.strftime('%Y%m%d')}"


def _field(*, error_code: str, error_reason: str) -> str:
    return json.dumps(
        {
            "error_code": error_code,
            "error_reason": error_reason,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _parse_field(raw: str) -> tuple[str, str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _UNKNOWN, raw[:160] or _UNKNOWN
    if not isinstance(data, dict):
        return _UNKNOWN, _UNKNOWN
    return (
        _clean(data.get("error_code"), max_len=96),
        _clean(data.get("error_reason"), max_len=160),
    )


async def record_radio_auto_skip_reason(
    *,
    error_code: str | None,
    error_reason: str | None,
    now: datetime | None = None,
) -> None:
    code = _clean(error_code, max_len=96)
    reason = _clean(error_reason, max_len=160)
    day = now or datetime.now(UTC)
    key = _day_key(day)
    try:
        redis = get_redis_client()
        pipe = redis.pipeline()
        pipe.hincrby(key, _field(error_code=code, error_reason=reason), 1)
        pipe.expire(key, _TTL_SECONDS)
        await pipe.execute()
    except Exception:
        logger.exception("radio_auto_skip_reason_record_failed")


async def get_radio_auto_skip_reason_stats(
    *,
    days: int = 7,
    limit: int = 10,
    now: datetime | None = None,
) -> list[RadioAutoSkipReasonStat]:
    days = max(1, min(days, 30))
    limit = max(1, min(limit, 50))
    today = now or datetime.now(UTC)
    keys = [_day_key(today - timedelta(days=offset)) for offset in range(days)]
    totals: dict[tuple[str, str], int] = {}
    try:
        redis = get_redis_client()
        for key in keys:
            rows = await redis.hgetall(key)
            for raw_field, raw_count in rows.items():
                field = (
                    raw_field
                    if isinstance(raw_field, str)
                    else raw_field.decode()
                )
                code, reason = _parse_field(field)
                totals[(code, reason)] = totals.get((code, reason), 0) + int(
                    raw_count or 0
                )
    except Exception:
        logger.exception("radio_auto_skip_reason_stats_failed")
        return []
    ranked = sorted(
        totals.items(),
        key=lambda item: (-item[1], item[0][0], item[0][1]),
    )
    return [
        {
            "error_code": code,
            "error_reason": reason,
            "count": count,
        }
        for (code, reason), count in ranked[:limit]
    ]
