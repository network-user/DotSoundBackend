"""Thin import adapter for the track lifecycle policy.

This module is the only file in the backend that talks to
``dotsound_private_core.services.track_lifecycle_policy``. It
re-exports the symbols backend code is allowed to call. Doing it
in one place keeps the public/private boundary search-friendly
and makes the contract obvious to whoever maintains PrivateCore.

Required PrivateCore contract (must exist in
``dotsound_private_core.services.track_lifecycle_policy``):

* ``TRACK_HARD_DELETE_BATCH_LIMIT: int`` -- max rows the cron may
  consider per run.
* ``valid_track_delete_reasons() -> frozenset[str]`` -- allowed
  values for ``Track.deleted_reason``. Backend validates against
  this set before writing to the column.
* ``should_hard_delete_track(deleted_at, reason, *, now=None)
  -> bool`` -- the only fact the cron needs.
* ``grace_period_seconds(reason) -> int`` -- used by the UI
  countdown ("restorable for X more days").

The actual numbers (per-reason grace, scoring, fallback ordering)
stay opaque. Backend never inspects them.
"""

from __future__ import annotations

from dotsound_private_core.services.track_lifecycle_policy import (
    TRACK_HARD_DELETE_BATCH_LIMIT,
    grace_period_seconds,
    should_hard_delete_track,
    valid_track_delete_reasons,
)

__all__ = (
    "TRACK_HARD_DELETE_BATCH_LIMIT",
    "grace_period_seconds",
    "should_hard_delete_track",
    "valid_track_delete_reasons",
)
