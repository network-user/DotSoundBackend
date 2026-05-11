# DotSoundBackend AI Boundary Policy

## Purpose

This repository is a public showcase. Sensitive business logic is
implemented in `DotSoundPrivateCore`.

## Architecture Model (Telegram-style)

The project follows the Telegram open-source model:

1. **Open client** -- frontend (React Mini App) and public Backend
   are maximally readable. Modules, services, UI, and network
   requests are organized in clear separate layers.
2. **Private core-server** -- all business logic, auth policy,
   anti-abuse, scoring, and moderation rules live in
   `DotSoundPrivateCore`, which does not reveal implementation
   details. Backend imports decisions from PrivateCore and applies
   them via Redis/DB/HTTP.
3. **Config separation** -- configuration, routing, and auth wiring
   are separated from business logic. All settings come from
   `.env` via `app/config.py` (pydantic-settings). Never use
   `os.environ` directly.
4. **Client-server boundary** -- the frontend can be built and
   verified independently (`cd frontend && npm run build`). It
   communicates with the backend exclusively through `/api/v1/`
   REST endpoints and WebSocket. No shared runtime state.

## Public Zone

- FastAPI route wiring and public API contracts.
- Pydantic schemas, ORM models, and repository layer.
- App bootstrap and infra wiring.
- Frontend Mini App UI and user-visible behavior.

## Private Zone (lives in `DotSoundPrivateCore`)

- Internal auth flow rules and OTP generation.
- Internal bridge contracts and secret-header policy.
- Anti-abuse, scoring, risk, and content moderation rules.
- Recommendation algorithms (collaborative, content-based, feed).
- ML pipelines (embeddings, genre classification, similarity).
- Monetization and subscription logic.
- Private analytics algorithms.
- Production-only privileged automation.

## Mandatory Rules For Any AI Agent

1. Do not move private logic into this repository.
2. Do not hardcode internal bridge constants in public modules.
3. If zone classification is ambiguous, stop and ask for approval.
4. Keep external API behavior backward-compatible during migrations.
5. Implement private rules via `dotsound_private_core` only.
6. Backend may create thin adapter services that call PrivateCore,
   but algorithms and business rules must stay in PrivateCore.
7. Do not implement recommendation, scoring, ML, or anti-abuse
   logic directly in this repository.

## Legal Readiness Rules

- Keep `UGC`, `licensed`, and `external-source` media flows distinct in
  code and user-facing text.
- Do not rely on `source` alone when media needs legal/product
  separation; use explicit fields like `catalog_type` and
  `access_mode`.
- Do not claim that DotSound does not store audio if any `UGC` flow
  stores audio in project-controlled infrastructure.
- Changes touching `upload`, `import`, `playback`, `complaints`,
  `recommendation`, or legal UI must be checked against `LEGAL.md` and
  `docs/legal/*.md`.
- If complaint fields exist in schemas or models, propagate them
  consistently through the route, service, repository, tests, and UI.
- Keep ordinary user complaints and rightsholder notices separate at
  the UX level whenever possible.
- Treat own playback over third-party stream URLs as a high-risk
  product mode; do not describe it as low-risk `source-first`.

## Frontend Exposure Policy

- Frontend code is public by design.
- Do not place secrets, internal tokens, or privileged contracts into
  frontend code.
- Security-sensitive decisions must run on backend/private core.

## Source Attribution Exception (artist enrichment, lyrics, track-info)

For the artist info card, the lyrics panel, and the track-info panel
the Backend and Mini App MAY display the human-readable name of an
external source and (where applicable) a direct attribution link.
These are deliberate, narrow exceptions to the general black-box rule
for three specific cascades only.

### Covered cascades

1. **Artist enrichment** — `source_profiles[].source_name`,
   `source_page_url`. Returned by PrivateCore.
2. **Lyrics provider attribution** — `source_name` on the lyrics
   response payload (if PrivateCore chooses to return one). Plus a
   feature-flag env-var name (e.g. `LYRICS_PROVIDER_NAME`) that the
   Backend adapter reads only to forward as a selector into
   PrivateCore. No URL attribution required.
3. **Track-info provider attribution** — same shape as (2) for the
   track-info response.

### Constraints that still apply

1. Only public-facing labels (`source_name`) and (for artist
   enrichment) the `source_page_url` returned by PrivateCore may be
   shown. Internal stage names, scoring weights, fallback ordering,
   rate limits, prompts, model identifiers, and any other pipeline
   internals MUST NOT be leaked.
2. Env-var values (provider keys, secrets) live only in
   PrivateCore's own `.env` / `.env.example`. The Backend env-flag
   name is the one exception — and it must only carry the public
   selector name (e.g. `yandex`, `generic`), never credentials.
3. Other PrivateCore cascades (recommendations, anti-abuse, scoring,
   moderation, etc.) keep the strict opaque rule.
4. New external sources MUST not be added to the public attribution
   list without an explicit policy review.
5. Log lines, commit messages, and TODO entries for the three
   covered cascades MAY name the external provider only when the
   mention is about **integration wiring** (env-flag, feature toggle,
   user-visible label). Algorithmic details — how the provider is
   called, how results are post-processed, how confidence is scored —
   remain inside PrivateCore and must not surface here.

## Classification Guide

### Decision tree: where does this code belong?

1. Is it a **security/auth constant** (TTL, max attempts, cooldown,
   internal IP ranges, token scope, TOTP window)? -> PrivateCore
2. Is it a **decision function** that uses those constants
   (should burn code? should cooldown? is internal IP?)? -> PrivateCore
3. Is it **anti-abuse logic** (disposable email check, Tor detection,
   spam rules, content filter rules)? -> PrivateCore
4. Is it **content moderation policy** (auto-hide threshold, report
   escalation rules)? -> PrivateCore
5. Is it **scoring/ranking/recommendation** algorithm? -> PrivateCore
6. Does it **call Redis, DB, S3, HTTP, or import a framework**?
   -> Backend (thin adapter importing PrivateCore decisions)
7. Is it **Pydantic schema, ORM model, or SQL query**? -> Backend
8. Is it **rate limit decorator value** (visible in 429 headers)?
   -> Backend (not secret)
9. Is it **upload/file size limit** (product config, not algorithm)?
   -> Backend

### Integration pattern

PrivateCore exposes:
  - Constants (thresholds, TTLs, prefixes)
  - Pure decision functions (inputs -> bool/value)
  - No framework imports, no I/O

Backend creates thin adapters:
  - Imports constants and decisions from PrivateCore
  - Applies them via Redis/DB/HTTP calls
  - Never hardcodes security constants locally

### Examples

PRIVATE (PrivateCore):
  - `FALLBACK_MAX_ATTEMPTS = 5`
  - `def should_burn_code(attempts: int) -> bool`
  - `def is_disposable_email(email: str) -> bool`
  - `TOR_REDIS_KEY = "tor_exit_nodes"`

PUBLIC (Backend adapter):
  - `attempts = await redis.incr(attempts_key)`
  - `if should_burn_code(attempts): await redis.delete(code_key)`
  - Redis/DB orchestration calling PrivateCore decisions

## Outbound HTTP Layer (Opaque)

All external HTTP traffic from PrivateCore — to music providers,
artist info sources, lyrics providers, library APIs — flows through
a single internal *outbound layer* that lives **only** in
`DotSoundPrivateCore`. Its responsibilities (IP rotation, transport
fingerprinting, per-service throttling, identity quarantine, retry
policy) are not part of the public Backend's surface.

Backend code, comments, log strings, docstrings, and commit
messages MUST NOT name:

* the specific transport technology used for outbound rotation
  (e.g. the daemon, control protocol or library names);
* the specific HTTP backend library used for fingerprint
  impersonation;
* the specific commercial proxy provider in use, if any;
* per-service tuning knobs (token-bucket rates, breaker thresholds).

Backend may reference the layer only through opaque names:

* the env var `OUTBOUND_PROFILE` (string; selects an internal
  preset);
* the admin endpoint `GET /api/v1/admin/system/outbound-status`,
  which returns a JSON snapshot the dashboard renders;
* the import path `dotsound_private_core.services.outbound`, treated
  as an opaque black box.

If a request needs a new external service, add the service profile
inside PrivateCore. Do not surface its proxy / rate-limit / breaker
choices in this repository.

## Storage Dedup (Cross-User, Content-Addressed)

Audio and HLS storage is content-addressed by SHA-256 of the
original source file (`source_sha256`). Multiple Tracks (across all
users) may share one `audio_blobs` row and one HLS bundle. The unique
constraint `(uploaded_by_id, blob_id)` has been dropped; deduplication
is transparent and never surfaces "this file already belongs to user
X" to the client.

Concurrency contract:

* `/upload/.../complete` computes `source_sha256` by streaming the
  assembled multipart object and writes it onto the Track.
* If an `AudioBlob` already exists for that hash, the transcode is
  skipped and the existing blob (+ HLS) is attached immediately.
* If not, `transcode_and_upload` runs; on completion it tags the
  fresh `AudioBlob` with `source_sha256` and reconciles every
  pending Track that claimed the same source.
* The daily `audio-blob-orphan-gc` job reconciles `audio_blobs`
  rows, `blobs/...` S3 keys, and `hls-blobs/...` prefixes, deleting
  orphans older than a safety window.

## Enforcement

- CI runs `scripts/check_boundary_policy.py`.
- CODEOWNERS protection is required for boundary docs and guardrails.
- Secret scanning runs in CI for every PR and push.

