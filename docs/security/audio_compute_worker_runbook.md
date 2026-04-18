# Audio-compute worker — operator runbook

This document explains how to provision and run a remote
audio-compute worker against a DotSound backend. The worker
daemon itself ships inside the private core package and is not
documented here; this runbook covers only the backend-facing
interface and the hardening checklist that every operator must
complete before turning a machine into a worker node.

## Provisioning a new worker

1. Open the admin panel → **Audio-compute** → **Add worker**.
2. Fill in a human-readable name and pick the profile
   (`cpu_light` or `gpu_full`). Only these two values are
   accepted today.
3. Backend generates a random secret and shows it **once**. Copy
   it immediately to the target host's OS credential store:
   - Windows: *Credential Manager → Windows Credentials →
     Add a generic credential*.
   - macOS: `security add-generic-password -a dotsound-worker \
       -s dotsound-worker -w <secret>`.
   - Linux: `secret-tool store --label='dotsound-worker' \
       service dotsound-worker`.
4. The backend database stores only a SHA-256 hash of the
   secret. If it is lost, rotate it from the admin panel — the
   old hash is invalidated immediately.

## Running the daemon

Only start the daemon from an account that is **not** a local
admin. Give the working directory `0700` on Unix-like systems.

Minimum environment variables the daemon expects:

| Variable              | Purpose                                |
|-----------------------|----------------------------------------|
| `DOTSOUND_BACKEND_URL`| Base URL, e.g. `https://api.example`.  |
| `DOTSOUND_WORKER_ID`  | The `w_...` identifier from step 2.    |
| `DOTSOUND_WORKER_SECRET` | Retrieved from the OS keyring.      |

A minimal `systemd` unit is enough on Linux. Add
`NoNewPrivileges=yes`, `ProtectSystem=strict`, and
`RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6`.

## Outbound firewall

The worker only needs two destinations:

- `api.<your-host>` on `443/tcp` — backend.
- `s3.<your-host>` on `443/tcp` — audio delivery.

Block everything else outbound so a compromise stays confined.

## Revocation and incident response

- Lost laptop? Revoke in the admin panel. The next request from
  that worker returns 404.
- Suspect the secret leaked? Use **Rotate secret** and reissue
  the new value over a trusted channel. Old signatures become
  invalid immediately.
- Unusual audit log patterns (many `auth_fail`, claim spam)
  trigger admin alerts and can auto-quarantine the worker.

## What the worker is allowed to do

The worker can only:

- Heartbeat.
- Claim a queued job matching its profile.
- Send progress updates for that specific job.
- Return a final result (or mark the job failed).

Anything else — including reading or writing user data — is
rejected by the backend regardless of the signed headers.
