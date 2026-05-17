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
  (`app/api/v1/tracks/playback.py`) and the background audio-cache
  worker (`app/services/audio_cache_worker.py`) both route audio CDN
  requests through the pool, sharing capacity caps and quarantine
  state. They both fall back to the server's native egress when no
  proxy is available or healthy. Tor is intentionally not on this
  path. Sticky binding uses ``make_sticky_key(track_id, stream_url)``
  so different transcodings of the same track form separate buckets.
- Prometheus surface: ``streaming_egress_picks_total``,
  ``streaming_egress_quarantine_total``,
  ``streaming_egress_exhausted_total``,
  ``streaming_egress_in_flight``,
  ``streaming_egress_failure_ratio``. Labels stay
  low-cardinality (egress identity = ``direct`` or
  ``scheme://host:port``).
- Catalog/API path (``api-v2.soundcloud.com`` resolve / search /
  transcoding metadata) keeps the legacy OutboundClient pool
  (Tor / static proxies) as the primary egress. When every
  identity in the pool is quarantined and
  ``SC_CATALOG_DIRECT_FALLBACK_ON_EXHAUSTION`` is on (default),
  ``sc_browser_session._direct_get_fallback`` performs one
  last-resort GET from the server's native IP. Counted via
  ``sc_catalog_direct_fallback_total{result}``.

## Tor Circuit Auto-Recovery

- After ``OutboundExhaustedError`` keeps firing for the same
  outbound service ``TOR_RECOVERY_FAILURE_THRESHOLD`` times in a row
  (default 3), Backend (`app/services/tor_recovery.py`) issues one
  forced NEWNYM signal via ``TorPool.force_newnym`` and clears the
  PrivateCore burned-IP quarantine via
  ``reset_outbound_quarantine``. Throttled by
  ``TOR_RECOVERY_MIN_INTERVAL_S`` (default 60s) — Tor itself
  rate-limits NEWNYM and silently drops signals that arrive too fast.
- Split of responsibilities:
  - PrivateCore exposes ``reset_outbound_quarantine() -> int`` that
    drops every burned identity from the in-memory cache. The
    decision *whether* to call it lives in Backend (the recovery
    loop and the periodic NEWNYM callback). PrivateCore only owns
    the storage shape.
  - Backend ``TorPool.force_newnym(reason, cooldown_s)`` rotates
    every circuit's exit IP and triggers the registered
    NEWNYM-callbacks (which include
    ``reset_audio_proxy_clients`` and
    ``reset_outbound_quarantine``).
  - Backend ``tor_recovery.note_outbound_exhaustion(service)``
    counts consecutive exhaustions per-service and triggers the
    pair of operations above when the threshold is reached.
    Counter is reset by
    ``tor_recovery.note_outbound_success(service)`` after a clean
    OutboundClient call.
- Prometheus surface: ``tor_recovery_triggered_total`` (Counter).
  Alert ``TorRecoveryFiringTooOften`` (warning, > 1/min for 15m)
  catches the case where SC bans Tor exits faster than NEWNYM can
  rotate, indicating residential proxies or longer quarantine TTLs
  are needed.

## Streaming Alerts

- Prometheus alert rules live in
  ``infra/prometheus/streaming_alerts.yml`` and are wired in via
  ``rule_files`` in ``infra/prometheus/prometheus.yml``. The file
  is mounted by ``docker-compose.observability.yml``. Coverage:
  - ``SoundCloudCatalogDirectFallbackFailing`` (page) — direct
    fallback errors > 1/min for 5m. Action: provision residential
    proxies for the SC catalog or extend the quarantine cooldown.
  - ``SoundCloudCatalogDirectFallbackElevated`` (warning) — any
    direct fallback > 2/min for 15m. Capacity-planning signal.
  - ``StreamingEgressPoolExhausted`` (page) — every streaming
    proxy quarantined > 1/min for 5m.
  - ``StreamingEgressHighFailureRatio`` (warning) — single egress
    > 50% failure for 10m (likely a dead proxy entry).
  - ``TorRecoveryFiringTooOften`` (warning) — see above.

## Non-Goals For Slice-1

- No migration of websocket manager and realtime orchestration.
- No API contract changes for public endpoints.
- No migrations that require frontend protocol changes.

