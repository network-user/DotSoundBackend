"""Schemas for offline-cache eligibility endpoints.

These models are the contract between the backend and the mini-app
service worker / download flow. Reason codes are stable strings —
``OfflineEligibilityReason`` enumerates every value that may appear
in API responses so the frontend can type-check exhaustively.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class OfflineEligibilityReason(str, Enum):
    """Stable reason codes returned by the eligibility endpoints.

    Values mirror reason-code constants exported by the offline
    policy adapter, plus two control-flow codes produced by the
    backend itself (``not_found`` and ``forbidden``) so a batch
    response can describe per-track failures uniformly.
    """

    OK = "ok"
    THIRD_PARTY_STREAM = "third_party_stream"
    OFFICIAL_EMBED = "official_embed"
    EXTERNAL_REFERENCE = "external_reference"
    UNKNOWN_MODE = "unknown_mode"
    TRACK_TOO_LARGE = "track_too_large"
    POLICY_UNAVAILABLE = "policy_unavailable"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    # ``UNKNOWN_ACCESS_MODE`` is the fallback emitted by the policy
    # for tracks whose ``access_mode`` is empty or unrecognised.
    UNKNOWN_ACCESS_MODE = "unknown_access_mode"


class OfflineEligibilityResponse(BaseModel):
    allowed: bool
    reason: str = Field(
        description=(
            "Reason code; one of the values in "
            "``OfflineEligibilityReason`` (forward-compatible string)."
        ),
    )
    max_track_bytes: int
    max_total_bytes_per_user: int


class OfflineEligibilityBatchRequest(BaseModel):
    track_ids: list[int] = Field(..., max_length=200)


class OfflineEligibilityBatchItem(BaseModel):
    allowed: bool
    reason: str


class OfflineEligibilityBatchResponse(BaseModel):
    items: dict[str, OfflineEligibilityBatchItem]
    max_track_bytes: int
    max_total_bytes_per_user: int
