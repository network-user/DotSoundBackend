"""Transport adapter for raw-event retention decisions.

Backend boundary for asking PrivateCore how long raw rows in
high-volume event tables (``listen_events`` first, others later)
should be kept before being folded into a daily aggregate.

If the PrivateCore implementation is not yet available, the adapter
falls back to a conservative default of 30 days so existing analytics
windows continue to work.

Contract for PrivateCore:

    dotsound_private_core.services.event_retention_policy:
        LISTEN_EVENT_RAW_RETENTION_DAYS: int
        def listen_event_aggregation_batch_size() -> int: ...
"""

from __future__ import annotations

_DEFAULT_RETENTION_DAYS = 30
_DEFAULT_AGG_BATCH = 5000

try:
    from dotsound_private_core.services import (  # type: ignore[import-not-found]
        event_retention_policy as _policy,
    )

    _HAS_POLICY = True
except ImportError:
    _policy = None  # type: ignore[assignment]
    _HAS_POLICY = False


def listen_event_raw_retention_days() -> int:
    if _HAS_POLICY:
        return int(
            getattr(
                _policy,
                "LISTEN_EVENT_RAW_RETENTION_DAYS",
                _DEFAULT_RETENTION_DAYS,
            )
        )
    return _DEFAULT_RETENTION_DAYS


def listen_event_aggregation_batch_size() -> int:
    if _HAS_POLICY:
        fn = getattr(_policy, "listen_event_aggregation_batch_size", None)
        if callable(fn):
            return int(fn())
    return _DEFAULT_AGG_BATCH


def policy_available() -> bool:
    return _HAS_POLICY
