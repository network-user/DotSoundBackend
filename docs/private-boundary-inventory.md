# DotSoundBackend Private Boundary Inventory

## Scope

This file documents the public/private split for the source-available
Backend showcase. It intentionally describes boundaries, not private
implementation details.

## Public In DotSoundBackend

- HTTP route declarations and request parsing in `app/api`.
- Public schemas and API contracts in `app/schemas`.
- ORM models and DB repositories in `app/models` and
  `app/repositories`.
- App bootstrap, dependency injection, S3/DB/Redis wiring, logging, and
  observability adapters.
- Frontend serving and Mini App static delivery.
- Backend orchestration around queues, jobs, storage, and admin tools.

## Private In DotSoundPrivateCore

`DotSoundPrivateCore` remains closed and is not published with the
showcase repositories. It owns security-sensitive and product-sensitive
decisions, including:

- Auth and internal bridge policy.
- Anti-abuse and moderation decisions.
- Recommendation, scoring, ranking, and personalization decisions.
- Upload/file validation policies and safety allowlists.
- External-source, outbound, and provider-selection strategy.
- ML/ASR quality policy and fallback decisions.
- Retention/lifecycle thresholds and other product guardrails.

## Backend Adapter Contract

Backend may import stable functions or constants from PrivateCore and
apply them to DB/Redis/S3/HTTP state. Backend must not duplicate private
rules locally and must not expose sensitive policy internals through
docs, logs, OpenAPI schemas, or frontend bundles.

Allowed public wording:

- "Backend asks PrivateCore for a decision."
- "The decision is policy-driven and lives in the private core."
- "Backend owns storage, queues, and API transport."

Avoid public wording:

- Sensitive policy tuning.
- Internal cascade, routing, or model-selection details.
- Service-specific operational strategy.
- Internal module names when the module name reveals a private strategy.

## Current Known Public Adapters

- Auth and web-auth flows call PrivateCore for code generation and
  security policy.
- Upload/file validation calls PrivateCore for allow/deny decisions.
- Recommendations and radio endpoints call PrivateCore for ranking and
  queue decisions.
- Playback, offline caching, and lifecycle services call PrivateCore for
  policy decisions while Backend handles storage and streaming.
- Compute-worker APIs use PrivateCore-owned contracts and Backend-owned
  HMAC/DB/Redis orchestration.

## Non-Goals

- This document is not a PrivateCore module inventory.
- This document does not define implementation details for algorithms,
  provider integrations, scoring, or anti-abuse.
- This document does not make the public repositories standalone; they
  remain showcase repositories that require the private package for full
  local execution.
