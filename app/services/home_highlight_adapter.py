"""Thin import adapter for the home-highlight picker policy.

Backend talks to
``dotsound_private_core.services.home_highlight_policy`` only
through this file. Keeps the public/private boundary easy to
audit.

Required PrivateCore contract (must exist):

* ``HOME_HIGHLIGHT_TTL_SECONDS: int``
* ``VALID_KINDS: frozenset[str]``
* ``HighlightCandidate`` dataclass
* ``HighlightChoice`` dataclass
* ``pick_home_highlight(candidates, *, viewer_has_listen_history)``
* Reason-code constants ``KIND_*``.
"""

from __future__ import annotations

from dotsound_private_core.services.home_highlight_policy import (
    HOME_HIGHLIGHT_TTL_SECONDS,
    KIND_FORGOTTEN_TREASURES,
    KIND_PERSONALIZED,
    KIND_STAFF_PICK,
    KIND_WEEKLY_TOP,
    KIND_YOUR_TOP,
    VALID_KINDS,
    HighlightCandidate,
    HighlightChoice,
    pick_home_highlight,
)

__all__ = (
    "HOME_HIGHLIGHT_TTL_SECONDS",
    "HighlightCandidate",
    "HighlightChoice",
    "KIND_FORGOTTEN_TREASURES",
    "KIND_PERSONALIZED",
    "KIND_STAFF_PICK",
    "KIND_WEEKLY_TOP",
    "KIND_YOUR_TOP",
    "VALID_KINDS",
    "pick_home_highlight",
)
