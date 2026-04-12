# DotSoundBackend Public Release Cut

## Included In Public Repository

- API route wiring and schemas.
- Data models and repositories.
- Non-sensitive services and app bootstrap.
- Frontend Mini App UI and build pipeline.
- Tests and developer tooling.

## Excluded Or Delegated To Private Core

- Internal secret-header transport contracts.
- One-time web auth private helper rules.
- Internal bot bridge URL policies.
- Anti-abuse/scoring and production-only risk rules.

## Pre-Publish Checklist

- [ ] No hardcoded internal bridge constants in public code.
- [ ] No secrets in source or frontend bundle.
- [ ] `docs/ai-boundary-policy.md` reflects current boundaries.
- [ ] CI guardrails and CODEOWNERS are enabled.
- [ ] License and usage restrictions are present.

