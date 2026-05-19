"""Transport adapter for promotion ranking/mixing decisions.

This module is the backend boundary that calls into PrivateCore for any
decisions about *how* promoted items are ordered and woven into organic
feeds. Backend only carries data; the rules live in PrivateCore.

If the PrivateCore implementation is not yet available, the adapter
falls back to safe pass-through defaults so the backend remains usable:
- ``select_active`` returns the promotions as the repository ordered
  them (priority desc, created_at desc).
- ``mix_in_feed`` returns the organic items unchanged (no in-feed
  injection). The "in_feed" surface effectively becomes a no-op until
  PrivateCore ships the mixing rules.

Contract for PrivateCore (see docs/promotion-policy-contract.md):

    dotsound_private_core.services.promotion_policy:
        def select_active(
            now: datetime,
            promotions: Sequence[PromotionView],
            surface: str,
            user_ctx: UserContext,
        ) -> list[PromotionView]: ...

        def mix_in_feed(
            organic: Sequence[FeedItem],
            promotions: Sequence[PromotionView],
            user_ctx: UserContext,
        ) -> list[FeedItem]: ...
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

try:
    from dotsound_private_core.services import (  # type: ignore[import-not-found]
        promotion_policy as _policy,
    )

    _HAS_POLICY = True
except ImportError:
    _policy = None  # type: ignore[assignment]
    _HAS_POLICY = False


@dataclass(frozen=True)
class PromotionView:
    id: int
    entity_type: str
    entity_id: int
    surfaces: tuple[str, ...]
    priority: int
    starts_at: datetime | None
    ends_at: datetime | None


@dataclass(frozen=True)
class UserContext:
    user_id: int | None
    locale: str | None = None


def select_active(
    now: datetime,
    promotions: Sequence[PromotionView],
    surface: str,
    user_ctx: UserContext,
) -> list[PromotionView]:
    if _HAS_POLICY:
        result = _policy.select_active(  # type: ignore[union-attr]
            now=now,
            promotions=promotions,
            surface=surface,
            user_ctx=user_ctx,
        )
        return list(result)
    return list(promotions)


def mix_in_feed(
    organic: Sequence[Any],
    promotions: Sequence[PromotionView],
    user_ctx: UserContext,
) -> list[Any]:
    if _HAS_POLICY:
        result = _policy.mix_in_feed(  # type: ignore[union-attr]
            organic=organic,
            promotions=promotions,
            user_ctx=user_ctx,
        )
        return list(result)
    return list(organic)


def policy_available() -> bool:
    return _HAS_POLICY
