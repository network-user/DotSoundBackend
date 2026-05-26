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

- [x] No hardcoded internal bridge constants in public code (spot-check; run `check_boundary_policy.py` in CI).
- [x] No secrets in source or frontend bundle (gitleaks in `policy-guardrails.yml`; local purge of `.env`/coverage/`_tmp_*` paths).
- [x] AI co-author trailers removed from public repo history (Backend, Bot, ComputeWorker).
- [x] `docs/ai-boundary-policy.md` reflects current boundaries (review on policy changes).
- [x] CI guardrails enabled (Backend/Bot/ComputeWorker: `policy-guardrails.yml` + gitleaks).
- [x] License present (Source-Available 1.0 in Backend, Bot, ComputeWorker).
- [ ] GitHub visibility set to Public (manual) for Backend, Bot, ComputeWorker only.
- [ ] PrivateCore remains private; no public remote fork with stale history.

