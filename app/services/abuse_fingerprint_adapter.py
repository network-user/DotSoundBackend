"""Thin import adapter for the anti-abuse fingerprint policy.

Backend talks to
``dotsound_private_core.services.abuse_fingerprint_policy`` only
through this file. Specific weights, thresholds and lockout
duration stay opaque -- backend only forwards the verdict.

Required PrivateCore contract:

* ``ABUSE_EVENT_RETENTION_SECONDS: int``
* ``LOCKOUT_DURATION_SECONDS: int``
* ``Decision`` enum (``PASS``, ``THROTTLE``,
  ``REQUIRE_CAPTCHA``, ``LOCKOUT``)
* ``AbuseSignals`` dataclass (signal aggregates)
* ``evaluate(signals, *, kind) -> Decision``
* ``EVENT_REGISTER`` / ``EVENT_LOGIN`` / ``EVENT_PLAY`` /
  ``EVENT_UPLOAD`` (event-kind constants)
"""

from __future__ import annotations

from dotsound_private_core.services.abuse_fingerprint_policy import (
    ABUSE_EVENT_RETENTION_SECONDS,
    EVENT_LOGIN,
    EVENT_PLAY,
    EVENT_REGISTER,
    EVENT_UPLOAD,
    LOCKOUT_DURATION_SECONDS,
    AbuseSignals,
    Decision,
    evaluate,
    should_lockout,
    should_require_captcha,
    should_throttle,
)

__all__ = (
    "ABUSE_EVENT_RETENTION_SECONDS",
    "AbuseSignals",
    "Decision",
    "EVENT_LOGIN",
    "EVENT_PLAY",
    "EVENT_REGISTER",
    "EVENT_UPLOAD",
    "LOCKOUT_DURATION_SECONDS",
    "evaluate",
    "should_lockout",
    "should_require_captcha",
    "should_throttle",
)
