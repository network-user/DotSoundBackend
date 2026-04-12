# DotSoundBackend AI Boundary Policy

## Purpose

This repository is a public showcase. Sensitive business logic is
implemented in `DotSoundPrivateCore`.

## Public Zone

- FastAPI route wiring and public API contracts.
- Pydantic schemas, ORM models, and repository layer.
- App bootstrap and infra wiring.
- Frontend Mini App UI and user-visible behavior.

## Private Zone

- Internal auth flow rules.
- Internal bridge contracts and secret-header policy.
- Anti-abuse, scoring, risk, and monetization rules.
- Production-only privileged automation.

## Mandatory Rules For Any AI Agent

1. Do not move private logic into this repository.
2. Do not hardcode internal bridge constants in public modules.
3. If zone classification is ambiguous, stop and ask for approval.
4. Keep external API behavior backward-compatible during migrations.
5. Implement private rules via `dotsound_private_core` only.

## Frontend Exposure Policy

- Frontend code is public by design.
- Do not place secrets, internal tokens, or privileged contracts into
  frontend code.
- Security-sensitive decisions must run on backend/private core.

## Enforcement

- CI runs `scripts/check_boundary_policy.py`.
- CODEOWNERS protection is required for boundary docs and guardrails.
- Secret scanning runs in CI for every PR and push.

