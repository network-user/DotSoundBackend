"""Thin import adapter for the offline-cache policy.

Backend talks to ``dotsound_private_core.services.offline_policy``
only through this file. Doing it in one place keeps the
public/private boundary search-friendly and makes the contract
easy to audit.

Required PrivateCore contract (must exist in
``dotsound_private_core.services.offline_policy``):

* ``OFFLINE_MAX_TRACK_BYTES: int``
* ``OFFLINE_MAX_TOTAL_BYTES_PER_USER: int``
* ``is_offline_allowed(*, catalog_type, access_mode,
  file_size_bytes=None) -> tuple[bool, str]``
* Reason-code constants (``REASON_OK``,
  ``REASON_THIRD_PARTY_STREAM``, ``REASON_OFFICIAL_EMBED``,
  ``REASON_EXTERNAL_REFERENCE``, ``REASON_UNKNOWN_MODE``,
  ``REASON_TRACK_TOO_LARGE``).

The reason codes are stable strings safe to forward to the
client; they never reveal internal scoring or cascade ordering.

If PrivateCore is unavailable (e.g. during local dev without the
private package installed), this adapter degrades to a
conservative fallback: ``is_offline_allowed`` always returns
``(False, "policy_unavailable")`` so the backend keeps serving
tracks online while disabling caching, instead of crashing the
whole API with import errors.
"""

from __future__ import annotations

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

REASON_POLICY_UNAVAILABLE = "policy_unavailable"

try:
    from dotsound_private_core.services.offline_policy import (
        OFFLINE_MAX_TOTAL_BYTES_PER_USER,
        OFFLINE_MAX_TRACK_BYTES,
        REASON_EXTERNAL_REFERENCE,
        REASON_OFFICIAL_EMBED,
        REASON_OK,
        REASON_THIRD_PARTY_STREAM,
        REASON_TRACK_TOO_LARGE,
        REASON_UNKNOWN_MODE,
        is_offline_allowed,
    )

    _policy_available = True
except Exception as exc:  # pragma: no cover
    logger.error(
        "offline_policy_unavailable",
        error=str(exc),
        error_type=type(exc).__name__,
    )

    OFFLINE_MAX_TRACK_BYTES = 0
    OFFLINE_MAX_TOTAL_BYTES_PER_USER = 0
    REASON_OK = "ok"
    REASON_THIRD_PARTY_STREAM = "third_party_stream"
    REASON_OFFICIAL_EMBED = "official_embed"
    REASON_EXTERNAL_REFERENCE = "external_reference"
    REASON_UNKNOWN_MODE = "unknown_mode"
    REASON_TRACK_TOO_LARGE = "track_too_large"

    def is_offline_allowed(  # type: ignore[no-redef]
        *,
        catalog_type: str,
        access_mode: str,
        file_size_bytes: int | None = None,
    ) -> tuple[bool, str]:
        return False, REASON_POLICY_UNAVAILABLE

    _policy_available = False


def is_offline_policy_available() -> bool:
    """Return whether the underlying policy module loaded successfully."""
    return _policy_available


__all__ = (
    "OFFLINE_MAX_TOTAL_BYTES_PER_USER",
    "OFFLINE_MAX_TRACK_BYTES",
    "REASON_EXTERNAL_REFERENCE",
    "REASON_OFFICIAL_EMBED",
    "REASON_OK",
    "REASON_POLICY_UNAVAILABLE",
    "REASON_THIRD_PARTY_STREAM",
    "REASON_TRACK_TOO_LARGE",
    "REASON_UNKNOWN_MODE",
    "is_offline_allowed",
    "is_offline_policy_available",
)
