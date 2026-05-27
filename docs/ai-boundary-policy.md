# DotSoundBackend AI Boundary Policy

## Purpose

This repository is published as a source-available engineering
showcase. It shows the public transport layer, API shape, storage
orchestration, frontend integration, and operational adapters. Sensitive
business rules remain in the private `DotSoundPrivateCore` package.

## Architecture Model

DotSound follows a public transport + private rules model:

1. **Public client and backend transport** — React Mini App, FastAPI
   routes, schemas, repositories, storage adapters, queues, and
   observability wiring are readable in this repository.
2. **Private rule engine** — product-sensitive decisions are imported
   from `DotSoundPrivateCore` and applied by Backend to DB/Redis/S3/HTTP
   state.
3. **Configuration boundary** — settings are loaded through
   `app/config.py`; secret values stay outside the repository.
4. **Frontend boundary** — frontend talks to Backend only through
   `/api/v1/` REST and WebSocket contracts.

## Public Zone

- Route declarations and request/response mapping.
- Pydantic schemas, ORM models, migrations, and repositories.
- Service orchestration around storage, queues, HTTP, and Redis.
- Mini App UI and public product flows.
- Public contracts for workers and internal adapters.

## Private Zone

PrivateCore owns:

- Auth, abuse, moderation, and security decisions.
- Recommendation, ranking, scoring, and personalization decisions.
- Upload/file safety policy and media lifecycle decisions.
- External-source, outbound, and provider-selection strategy.
- ML/ASR quality policy and fallback decisions.
- Product thresholds, TTLs, caps, and privileged automation rules.

## Rules For Agents

- Do not move private logic into this repository.
- Do not duplicate sensitive policy tuning or private decision logic in
  Backend.
- Backend may create thin adapters that call PrivateCore decisions and
  apply them to infrastructure state.
- If a change may cross the public/private boundary and the intent is
  unclear, stop and ask.
- Do not put secret values or private operational runbooks into docs,
  logs, OpenAPI schemas, frontend bundles, or commit messages.

## Legal Readiness Rules

- Keep `UGC`, `licensed`, and `external-source` media flows distinct in
  code and user-facing text.
- Do not claim DotSound never stores audio while any UGC upload flow
  stores audio in project-controlled infrastructure.
- Treat own playback over third-party stream URLs as high-risk until a
  separate legal review approves it.
- Changes touching upload, import, playback, complaints,
  recommendations, or legal UI must be checked against `LEGAL.md` and
  public legal drafts.

## Public Attribution Exception

User-facing UI may show a public source label or public source page URL
when that attribution is part of the product contract. This does not
allow leaking sensitive policy internals or operational strategy.

## Enforcement

- `scripts/check_boundary_policy.py` guards the public/private split.
- Secret scanning runs on public branches.
- Boundary docs should be reviewed when files importing PrivateCore are
  added, removed, or renamed.

