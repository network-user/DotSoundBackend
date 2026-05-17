# DotSoundBackend Private Boundary Inventory

## Scope

This file defines which parts of `DotSoundBackend` stay public and
which parts are owned by `DotSoundPrivateCore`.

## Public In DotSoundBackend

- HTTP route declarations and request parsing in `app/api`.
- Public schemas and API contracts in `app/schemas`.
- ORM models and DB repositories in `app/models` and
  `app/repositories`.
- App bootstrap and infrastructure wiring in `app/main.py`,
  `app/dependencies.py`, `app/core/db.py`, and `app/core/s3.py`.
- Frontend serving and Mini App static delivery.

## Private Candidates Migrated To DotSoundPrivateCore

- `app/api/v1/auth.py`
  - one-time code generation rules
  - IP masking and user-agent normalization rules
  - internal bot notification request shaping
- `app/services/import_service.py`
  - internal bot bridge URL and header rules
- `app/services/import_worker.py`
  - secure internal bot download URL and header rules
  - audio mime to extension normalization rules
  - import size guardrails

## Private Candidates Planned For Later Slices

- Anti-abuse and scoring policies.
- Production-only risk and moderation heuristics.
- Additional internal admin automation with privileged side effects.

## Recsys (listening language)

- Heuristics and score weights for listening-language affinity live in
  `DotSoundPrivateCore` (`recommendation_language_policy`,
  `recommendation_engine`, `scoring`). Cyrillic strata ratio, cold-start
  language affinity defaults, and whether Russian discovery boosting is
  always on are defined there (`RU_STRATIFICATION_ALWAYS`,
  `DEFAULT_CYRILLIC_STRATA_RATIO`, `cold_start_language_affinity_weights`).
- Backend supplies track metadata, aggregates `language_affinity` from
  history and `users.locale`, runs SQL candidate pools (including
  stratified Cyrillic vs global slices where applicable), and issues
  external discovery search queries.

## Streaming Egress Pool

- Decision rules for the third-party audio CDN streaming pool live in
  `DotSoundPrivateCore` (`streaming_egress_policy`). The policy module
  owns sticky-TTL, quarantine thresholds, exponential back-off, and the
  set of services that count as "audio CDN streaming". Decision
  functions are stateless: Backend passes a snapshot of in-flight
  counters and last-use timestamps and gets back the next egress to
  use plus an updated health record.
- Backend (`app/services/streaming_egress_pool.py`) owns the runtime
  state — per-egress in-flight counter, last-use timestamp, quarantine
  window, and the per-track sticky map — guarded by a single
  `threading.Lock`. The playback range proxy
  (`app/api/v1/tracks/playback.py`) routes audio CDN requests through
  the pool and falls back to the server's native egress when no proxy
  is available or healthy. Tor is intentionally not on this path.

## Non-Goals For Slice-1

- No migration of websocket manager and realtime orchestration.
- No API contract changes for public endpoints.
- No migrations that require frontend protocol changes.

