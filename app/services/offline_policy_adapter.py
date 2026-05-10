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
"""

from __future__ import annotations

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

__all__ = (
    "OFFLINE_MAX_TOTAL_BYTES_PER_USER",
    "OFFLINE_MAX_TRACK_BYTES",
    "REASON_EXTERNAL_REFERENCE",
    "REASON_OFFICIAL_EMBED",
    "REASON_OK",
    "REASON_THIRD_PARTY_STREAM",
    "REASON_TRACK_TOO_LARGE",
    "REASON_UNKNOWN_MODE",
    "is_offline_allowed",
)
