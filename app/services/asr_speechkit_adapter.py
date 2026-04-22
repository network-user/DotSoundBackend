"""Yandex SpeechKit Async Recognition adapter.

Tier 3 of the cascade. Wraps the public REST API:

    POST https://transcribe.api.cloud.yandex.net/speech/stt/v2/longRunningRecognize

Authentication uses an API key (cheap, easy to rotate). For the
operation polling phase we hit the LRO endpoint:

    GET https://operation.api.cloud.yandex.net/operations/{id}

Budget guard lives in `dotsound_private_core.services.asr_policy`;
this module just reads/writes the monthly Redis counter.

NOTE: actually shipping audio to Yandex moves the user's UGC
across borders. Don't enable this tier without first updating
LEGAL.md (see plan §8).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from dotsound_private_core.services.asr_policy import (
    estimate_speechkit_cost_rub,
    should_use_paid_asr,
)

from app.config import settings
from app.core.redis import get_redis_client

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

LONG_RUN_URL = (
    "https://transcribe.api.cloud.yandex.net"
    "/speech/stt/v2/longRunningRecognize"
)
OPERATION_URL_TPL = (
    "https://operation.api.cloud.yandex.net"
    "/operations/{op_id}"
)
SPENT_KEY_TEMPLATE = "speechkit_spent:{bucket}"
SPENT_TTL_SECONDS = 32 * 24 * 3600


class SpeechKitError(RuntimeError):
    pass


class SpeechKitDisabled(SpeechKitError):
    pass


class SpeechKitBudgetExhausted(SpeechKitError):
    pass


def _bucket() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m")


def _spent_key() -> str:
    return SPENT_KEY_TEMPLATE.format(bucket=_bucket())


async def get_monthly_spent_rub() -> float:
    redis = get_redis_client()
    raw = await redis.get(_spent_key())
    try:
        return float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


async def add_to_monthly_spent_rub(amount_rub: float) -> float:
    redis = get_redis_client()
    key = _spent_key()
    new_val = await redis.incrbyfloat(
        key, max(0.0, float(amount_rub))
    )
    await redis.expire(key, SPENT_TTL_SECONDS)
    try:
        from app.core.observability import (
            speechkit_budget_remaining_set,
            speechkit_spent_inc,
        )

        speechkit_spent_inc(amount_rub)
        speechkit_budget_remaining_set(
            max(
                0.0,
                float(
                    settings.yandex_speechkit_monthly_budget_rub
                )
                - float(new_val),
            )
        )
    except Exception:
        pass
    return float(new_val)


async def reset_monthly_spent() -> None:
    redis = get_redis_client()
    await redis.delete(_spent_key())


async def _check_gate(
    audio_seconds: float,
    *,
    force_paid: bool,
) -> None:
    spent = await get_monthly_spent_rub()
    ok, reason = should_use_paid_asr(
        enabled=settings.yandex_speechkit_enabled,
        monthly_spent_rub=spent,
        monthly_budget_rub=(
            settings.yandex_speechkit_monthly_budget_rub
        ),
        audio_seconds=audio_seconds,
        rate_rub_per_minute=(
            settings.yandex_speechkit_rate_rub_per_minute
        ),
        soft_per_job_limit_rub=(
            settings.yandex_speechkit_soft_per_job_limit_rub
        ),
        force_paid=force_paid,
    )
    if not ok:
        if reason == "speechkit_disabled":
            raise SpeechKitDisabled(reason)
        if reason in {
            "speechkit_no_budget",
            "speechkit_budget_exhausted",
        }:
            raise SpeechKitBudgetExhausted(reason)
        raise SpeechKitError(reason)


async def transcribe(
    audio_url: str,
    *,
    audio_seconds: float,
    language_code: str = "auto",
    correlation_id: str | None = None,
    force_paid: bool = False,
    poll_interval: float = 5.0,
    max_wait_seconds: int = 600,
) -> dict[str, Any]:
    """Run an async recognition for ``audio_url``.

    ``audio_url`` must be a publicly reachable HTTPS URL (Yandex
    will fetch it themselves). Backend usually generates a
    short-lived presigned MinIO URL for this.
    """
    await _check_gate(
        audio_seconds, force_paid=force_paid
    )
    if not settings.yandex_speechkit_api_key:
        raise SpeechKitDisabled("api_key_missing")

    payload: dict[str, Any] = {
        "config": {
            "specification": {
                "languageCode": language_code,
                "audioEncoding": "OGG_OPUS",
                "model": "general",
                "literature_text": True,
            },
        },
        "audio": {"uri": audio_url},
    }
    headers = {
        "Authorization": (
            f"Api-Key {settings.yandex_speechkit_api_key}"
        ),
        "Content-Type": "application/json",
    }
    if correlation_id:
        headers["x-request-id"] = correlation_id

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0)
    ) as client:
        resp = await client.post(
            LONG_RUN_URL,
            content=json.dumps(payload).encode(),
            headers=headers,
        )
        if resp.status_code >= 400:
            raise SpeechKitError(
                f"long_run_status_{resp.status_code}:"
                f"{resp.text[:200]}"
            )
        operation = resp.json()
        op_id = operation.get("id")
        if not isinstance(op_id, str) or not op_id:
            raise SpeechKitError(
                "missing_operation_id"
            )

        deadline = (
            asyncio.get_event_loop().time()
            + max_wait_seconds
        )
        while True:
            if (
                asyncio.get_event_loop().time()
                > deadline
            ):
                raise SpeechKitError("operation_timeout")
            await asyncio.sleep(poll_interval)
            poll = await client.get(
                OPERATION_URL_TPL.format(op_id=op_id),
                headers={
                    "Authorization": (
                        f"Api-Key "
                        f"{settings.yandex_speechkit_api_key}"
                    )
                },
            )
            if poll.status_code >= 400:
                raise SpeechKitError(
                    f"poll_status_{poll.status_code}"
                )
            data = poll.json()
            if not data.get("done"):
                continue
            if "error" in data:
                raise SpeechKitError(
                    f"operation_error:{data['error']}"
                )
            response = data.get("response") or {}
            chunks = response.get("chunks") or []
            text_parts: list[str] = []
            synced: list[dict[str, Any]] = []
            for chunk in chunks:
                alts = chunk.get("alternatives") or []
                if not alts:
                    continue
                best = alts[0]
                text = (best.get("text") or "").strip()
                if not text:
                    continue
                text_parts.append(text)
                start_str = chunk.get(
                    "channelTag"
                ) or "0"
                start_ms = 0
                try:
                    start_ms = int(
                        float(start_str) * 1000
                    )
                except (TypeError, ValueError):
                    pass
                synced.append(
                    {
                        "time_ms": start_ms,
                        "text": text,
                        "confidence": float(
                            best.get("confidence") or 0.0
                        ),
                    }
                )
            cost = estimate_speechkit_cost_rub(
                audio_seconds,
                settings.yandex_speechkit_rate_rub_per_minute,
            )
            await add_to_monthly_spent_rub(cost)
            logger.info(
                "speechkit_billed",
                cost_rub=cost,
                audio_seconds=audio_seconds,
            )
            return {
                "plain_text": "\n".join(text_parts),
                "synced_lines": synced or None,
                "sync_quality": (
                    "line" if synced else "none"
                ),
                "sync_profile": "speechkit_paid",
                "cost_rub": cost,
            }


__all__ = [
    "LONG_RUN_URL",
    "OPERATION_URL_TPL",
    "SpeechKitBudgetExhausted",
    "SpeechKitDisabled",
    "SpeechKitError",
    "add_to_monthly_spent_rub",
    "get_monthly_spent_rub",
    "reset_monthly_spent",
    "transcribe",
]
