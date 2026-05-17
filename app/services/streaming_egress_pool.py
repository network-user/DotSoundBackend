"""Streaming egress pool for third-party audio CDN byte-streams.

Backend adapter on top of the PrivateCore decision functions in
``streaming_egress_policy``. This module owns the runtime state
(in-flight counters, last-use timestamps, quarantine windows) and
provides a small synchronous API the playback proxy uses on every
audio request:

- :func:`pick_egress` — choose an egress for a new request, taking
  out the in-flight slot.
- :func:`finish_egress` — release the in-flight slot and record
  ok / failure outcome.

Egress URLs come from ``settings.streaming_proxy_out_urls_list``.
The empty list means "always direct"; a populated list rotates
through the proxies with sticky-per-track binding and exponential
quarantine (decision logic lives in PrivateCore).

The pool is in-process and resets on app restart. Multi-replica
deployments naturally average out — each pod manages its own slice
of egress capacity.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlsplit

import structlog
from dotsound_private_core.services.streaming_egress_policy import (
    MAX_CONCURRENT_PER_EGRESS,
    EgressHealth,
    EgressIdentity,
    EgressPickInputs,
    is_streaming_audio_service,
    pick_streaming_egress,
    record_egress_outcome,
    record_request_finished,
    record_request_started,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class StreamingEgressDecision:
    """One pick from :func:`pick_egress`.

    ``proxy_url`` is ``None`` for the direct egress. ``release`` MUST
    be called exactly once with ``ok=True/False`` once the streamed
    response either completed or errored, regardless of what path
    the caller took.
    """

    proxy_url: str | None
    egress_name: str
    sticky_key: str | None


def _identity_name(url: str | None) -> str:
    """Deterministic short label for an egress URL.

    Two URLs with the same scheme/host/port collapse to the same
    name. Credentials in the URL (``socks5://user:pass@host``) do
    not affect the identity — we still pick the same back-end IP.
    """
    if url is None:
        return "direct"
    parsed = urlsplit(url)
    host = parsed.hostname or "unknown"
    if parsed.port is None:
        return f"{parsed.scheme or 'tcp'}://{host}"
    return f"{parsed.scheme or 'tcp'}://{host}:{parsed.port}"


class StreamingEgressPool:
    """Per-process state container for the streaming egress pool."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._healths: dict[str, EgressHealth] = {}
        self._sticky: dict[str, tuple[str, float]] = {}

    def _identities_locked(
        self,
        proxy_urls: list[str],
        *,
        allow_direct: bool,
    ) -> list[EgressIdentity]:
        items: list[EgressIdentity] = []
        seen: set[str] = set()
        for raw in proxy_urls:
            name = _identity_name(raw)
            if name in seen:
                continue
            seen.add(name)
            items.append(EgressIdentity(url=raw, name=name))
        if allow_direct:
            items.append(EgressIdentity(url=None, name="direct"))
        return items

    def pick(
        self,
        *,
        proxy_urls: list[str],
        sticky_key: str | None,
        allow_direct_fallback: bool,
        max_concurrent: int = MAX_CONCURRENT_PER_EGRESS,
    ) -> StreamingEgressDecision | None:
        """Pick an egress and reserve one in-flight slot."""
        if not proxy_urls and not allow_direct_fallback:
            return None
        with self._lock:
            candidates = self._identities_locked(
                proxy_urls,
                allow_direct=allow_direct_fallback or not proxy_urls,
            )
            now = monotonic()
            sticky_entry = self._sticky.get(sticky_key) if sticky_key else None
            sticky_name = sticky_entry[0] if sticky_entry else None
            sticky_at = sticky_entry[1] if sticky_entry else None
            decision = pick_streaming_egress(
                EgressPickInputs(
                    candidates=candidates,
                    healths=self._healths,
                    now=now,
                    sticky_name=sticky_name,
                    sticky_at=sticky_at,
                    allow_direct_fallback=(
                        allow_direct_fallback or not proxy_urls
                    ),
                    max_concurrent_per_egress=max_concurrent,
                )
            )
            if decision is None:
                return None
            health = self._healths.get(decision.name, EgressHealth())
            self._healths[decision.name] = record_request_started(
                health=health, now=now
            )
            if sticky_key is not None:
                self._sticky[sticky_key] = (decision.name, now)
            return StreamingEgressDecision(
                proxy_url=decision.url,
                egress_name=decision.name,
                sticky_key=sticky_key,
            )

    def finish(
        self,
        decision: StreamingEgressDecision,
        *,
        ok: bool,
    ) -> None:
        """Release the slot and record the outcome."""
        with self._lock:
            now = monotonic()
            health = self._healths.get(decision.egress_name, EgressHealth())
            health = record_request_finished(health=health)
            health = record_egress_outcome(health=health, ok=ok, now=now)
            self._healths[decision.egress_name] = health
            if not ok and decision.sticky_key is not None:
                pinned = self._sticky.get(decision.sticky_key)
                if pinned is not None and pinned[0] == decision.egress_name:
                    # Drop the sticky binding so the next byte-range
                    # request rotates onto a healthier egress.
                    self._sticky.pop(decision.sticky_key, None)
        logger.info(
            "streaming_egress_finished",
            egress=decision.egress_name,
            ok=ok,
            sticky_key=decision.sticky_key,
            in_flight=health.in_flight,
            consecutive_failures=health.consecutive_failures,
        )

    def reset_for_tests(self) -> None:
        """Clear all state. Tests only."""
        with self._lock:
            self._healths.clear()
            self._sticky.clear()


_pool = StreamingEgressPool()


def get_streaming_egress_pool() -> StreamingEgressPool:
    return _pool


def is_audio_streaming_service(service: str | None) -> bool:
    """Re-export the PrivateCore predicate for Backend callers."""
    return is_streaming_audio_service(service)
