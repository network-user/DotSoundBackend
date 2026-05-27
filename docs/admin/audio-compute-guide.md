# Compute Worker — Admin Guide

This public-safe guide explains the admin surface for pull-based compute
workers without documenting sensitive policy or operational strategy.

Technical worker protocol: `docs/compute-worker-protocol.md`.

## What The Page Shows

The admin page groups worker operations into:

- Worker onboarding and registration.
- Global routing mode for compute jobs.
- Worker list and worker detail drawer.
- Job queues and per-job routing.
- Recent worker audit events.
- Health and troubleshooting signals.

The UI is rendered by `frontend/src/admin/routes/AudioComputeRoute.tsx`.

## Adding A Worker

1. Create a worker in the admin UI.
2. Copy the generated `WORKER_ID` and `WORKER_SECRET` once.
3. Place them in the worker's local `.env` file together with
   `WORKER_BACKEND_BASE_URL`.
4. Start the worker.
5. Confirm heartbeat and claim events in the worker table.

Treat `WORKER_SECRET` like a password. If it is lost or exposed, rotate
it from the admin UI and update the worker environment.

## Worker Security

- Backend-facing requests are HMAC signed.
- Worker IP ranges should be restricted to known egress CIDRs.
- Worker actions are audited.
- Dangerous admin actions require the normal admin security flow.
- Worker logs should keep redaction enabled outside local debugging.

## Job Routing

Admins can inspect queued/running jobs, adjust priority, pin a job to a
specific worker, release stale leases, or pause worker claims during
maintenance. The exact policy for which job should run where is owned by
Backend plus the private policy package.

## Troubleshooting

| Symptom | Likely area to check |
|---|---|
| Worker does not appear active | Heartbeat URL, worker secret, clock skew, network access |
| Job stays queued | Worker capability/profile, claim pause, allowed IP CIDRs |
| Result rejected | HMAC signature, job lease, payload shape |
| Repeated failures | Worker logs, audit events, input media availability |

## Public Showcase Notes

This document intentionally omits:

- Private cascade details.
- External service configuration.
- Paid processing budget knobs.
- Sensitive policy and operational tuning.

Those details belong to private operational runbooks and
`DotSoundPrivateCore`.
