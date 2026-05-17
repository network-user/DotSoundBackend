"""Tor circuit auto-recovery after sustained outbound exhaustion.

When ``OutboundExhaustedError`` keeps firing for the same service —
i.e. every Tor circuit and every static proxy is quarantined —
periodic NEWNYM (every ``tor_circuit_max_age_seconds``) is too slow
to keep the catalog usable. This module forces a one-shot NEWNYM as
soon as we see N consecutive exhaustions for a given service, with
a hard cooldown so we never hammer the Tor network.

Layering:

* The *decision* whether to recover (counter shape, threshold,
  cooldown) is configured in ``AppSettings`` and lives here in
  Backend; the threshold values are operational tuning knobs, not
  product policy, so they stay in ``app/config.py``.
* The *transport* — sending NEWNYM, clearing the in-memory burned-IP
  quarantine — is split: ``TorPool.force_newnym`` rotates the
  circuits, ``reset_outbound_quarantine`` (PrivateCore) clears the
  cache. We only call those primitives from here.

The whole module is process-local on purpose. Cross-pod coordination
would require Redis and is overkill: Tor NEWNYM is cheap, and worst
case every replica triggers it independently — Tor will throttle.
"""

from __future__ import annotations

import asyncio
import time

import structlog

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


_lock = asyncio.Lock()
_consecutive_exhaustions: dict[str, int] = {}
_last_recovery_at: float = 0.0


async def note_outbound_exhaustion(service: str) -> bool:
    """Record an ``OutboundExhaustedError`` for *service*.

    Returns ``True`` if this call triggered a forced Tor NEWNYM +
    quarantine reset, ``False`` otherwise. Callers should NOT branch
    behaviour on the return value — recovery is fire-and-forget. The
    boolean is exposed only for tests and metrics.
    """
    global _last_recovery_at
    if not settings.tor_recovery_enabled:
        return False
    if not settings.tor_pool_enabled:
        return False

    threshold = max(1, int(settings.tor_recovery_failure_threshold))
    min_interval = max(0.0, float(settings.tor_recovery_min_interval_s))

    async with _lock:
        count = _consecutive_exhaustions.get(service, 0) + 1
        _consecutive_exhaustions[service] = count
        if count < threshold:
            return False
        now = time.monotonic()
        elapsed = now - _last_recovery_at
        if elapsed < min_interval:
            logger.info(
                "tor_recovery_throttled",
                service=service,
                consecutive=count,
                elapsed=round(elapsed, 1),
                min_interval=min_interval,
            )
            return False
        _last_recovery_at = now
        _consecutive_exhaustions[service] = 0

    logger.warning(
        "tor_recovery_triggered",
        service=service,
        threshold=threshold,
    )
    return await _trigger_recovery(reason=f"exhaustion:{service}")


async def note_outbound_success(service: str) -> None:
    """Reset the consecutive-exhaustion counter on a clean call."""
    async with _lock:
        if service in _consecutive_exhaustions:
            _consecutive_exhaustions.pop(service, None)


async def reset_state_for_tests() -> None:
    """Drop the recovery counters and cooldown. Test-only."""
    global _last_recovery_at
    async with _lock:
        _consecutive_exhaustions.clear()
        _last_recovery_at = 0.0


async def _trigger_recovery(*, reason: str) -> bool:
    pool_signaled = await _force_newnym(reason=reason)
    if not pool_signaled:
        return False
    _record_metric()
    return True


async def _force_newnym(*, reason: str) -> bool:
    try:
        from app.services.tor_pool import get_tor_pool

        pool = get_tor_pool()
    except Exception as exc:
        logger.warning("tor_recovery_pool_unavailable", error=str(exc))
        return False
    if pool is None:
        logger.info("tor_recovery_pool_not_started")
        return False
    cooldown = max(0.0, float(settings.tor_recovery_min_interval_s))
    try:
        return await pool.force_newnym(
            reason=reason,
            cooldown_s=cooldown,
        )
    except Exception as exc:
        logger.error(
            "tor_recovery_force_newnym_failed",
            reason=reason,
            error=str(exc),
        )
        return False


def _record_metric() -> None:
    try:
        from app.core.observability import (
            tor_recovery_triggered_observed,
        )

        tor_recovery_triggered_observed()
    except Exception:
        pass
