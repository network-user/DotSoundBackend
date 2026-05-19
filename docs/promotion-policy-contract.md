# Promotion Policy Contract (PrivateCore)

## Status

Backend ships an opaque adapter at
`app/services/promotion_policy_adapter.py` that imports
`dotsound_private_core.services.promotion_policy` and falls back to
safe pass-through defaults when the module is missing.

When PrivateCore implements the contract below, the backend picks it
up automatically — no further backend changes required.

## Why this is private

The backend stores the *what* (which artist/track/playlist/album is
boosted, in which surfaces, with which window/priority). The rules
for *how* a boost is mixed into the organic feed — insertion
positions, anti-fatigue, dedupe with organic items, per-user
frequency caps — are ranking decisions and live in PrivateCore per
the black-box rule (`CLAUDE.md`, `docs/ai-boundary-policy.md`).

## Module location

```
dotsound_private_core/services/promotion_policy.py
```

## Data classes (mirror in PrivateCore)

```python
@dataclass(frozen=True)
class PromotionView:
    id: int
    entity_type: str            # 'artist'|'track'|'playlist'|'album'
    entity_id: int
    surfaces: tuple[str, ...]   # subset of allowed surfaces
    priority: int
    starts_at: datetime | None
    ends_at: datetime | None

@dataclass(frozen=True)
class UserContext:
    user_id: int | None
    locale: str | None = None
```

Backend imports the local dataclasses (defined in the adapter) and
passes them to PrivateCore. PrivateCore re-declares them (or
imports the same dataclasses if a shared contracts package exists).

## Required functions

### `select_active`

```python
def select_active(
    now: datetime,
    promotions: Sequence[PromotionView],
    surface: str,
    user_ctx: UserContext,
) -> list[PromotionView]:
    ...
```

Filters and orders the candidate promotions for a single surface
(`hero`, `section`, `in_feed`, `search_pin`). PrivateCore decides:

- per-user frequency caps (do not show the same promo to the same
  user more than N times per day),
- locale weighting (e.g. boost promo whose subtitle locale matches
  `user_ctx.locale`),
- jitter/A-B sampling,
- final tie-break ordering.

The backend has already filtered:

- inactive rows,
- rows whose `starts_at`/`ends_at` window does not include `now`,
- rows whose target entity is currently unavailable (track hidden,
  playlist private, album hidden, etc.).

### `mix_in_feed`

```python
def mix_in_feed(
    organic: Sequence[Any],
    promotions: Sequence[PromotionView],
    user_ctx: UserContext,
) -> list[Any]:
    ...
```

Injects promotion rows into an organic feed. Called by backend for
the `in_feed` surface only. Decides:

- which positions get promo slots (e.g. positions 3 and 13),
- minimum spacing between promo slots,
- dedupe (do not inject a promo for an item already organic in the
  same response),
- per-user diversification.

Currently the backend's `in_feed` surface is **not active** because
the recommendation pipeline does not yet call `mix_in_feed`. When
this module ships, wire the call into
`app/services/recommendation_service.py` next to the existing
candidate-fetch step. The wiring should:

1. Fetch active `in_feed` promotions via
   `PromotionService.get_for_surface("in_feed", ...)`.
2. Convert each `PromotionPublic` to a `PromotionView`.
3. Call `mix_in_feed(organic, views, user_ctx)`.
4. Return the merged list to the caller.

Backend will continue to record `impression` and `click` events
through the existing public events endpoint
(`POST /api/v1/promotions/{id}/event`).

## What stays in backend

- DB schema and CRUD for `promotions` and `promotion_events`.
- Admin UI / API for picking *what* to promote.
- Entity availability filtering (track hidden, playlist private,
  etc.) — pure SQL transport, not a ranking decision.
- Event ingestion and stats aggregation (counts).
- Pass-through ordering when PrivateCore is not yet present.

## What must not leak

- Internal stage names, scoring weights, fallback ordering, prompts,
  per-tier rate limits — none of these appear in this repo,
  including in comments, log strings, env-var names, or commit
  messages. Follow the existing black-box rule (`AGENTS.md` →
  "Чёрный ящик для PrivateCore").
