"""Transport adapter for cover regeneration decisions.

Backend boundary for asking PrivateCore whether a given track cover
should be re-encoded under the current sweep. Backend only carries
mechanical metadata; the policy lives in PrivateCore.

If the PrivateCore implementation is not yet available, the adapter
falls back to safe pass-through defaults so the backend remains usable:
- ``should_regen_cover`` returns ``True`` for every row, letting the
  worker re-encode unconditionally. The Redis cursor is the only
  thing that prevents double-work on a single sweep.

Contract for PrivateCore:

    dotsound_private_core.services.cover_regen_policy:
        def should_regen_cover(
            cover_key: str,
            updated_at: datetime | None,
            now: datetime,
        ) -> bool: ...
"""

from __future__ import annotations

from datetime import datetime

try:
    from dotsound_private_core.services import (  # type: ignore[import-not-found]
        cover_regen_policy as _policy,
    )

    _HAS_POLICY = True
except ImportError:
    _policy = None  # type: ignore[assignment]
    _HAS_POLICY = False


def should_regen_cover(
    cover_key: str,
    updated_at: datetime | None,
    now: datetime,
) -> bool:
    if _HAS_POLICY:
        return bool(
            _policy.should_regen_cover(  # type: ignore[union-attr]
                cover_key=cover_key,
                updated_at=updated_at,
                now=now,
            )
        )
    return True


def policy_available() -> bool:
    return _HAS_POLICY
