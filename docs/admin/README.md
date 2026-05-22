# Admin Panel

Operator runbook for the DotSound admin panel.

## Where it lives

- Backend: routes under `/api/v1/{ADMIN_PANEL_PATH}/*`, code in
  [`app/api/v1/admin/`](../../app/api/v1/admin/).
- Frontend: separate code-split chunk under
  [`frontend/src/admin/`](../../frontend/src/admin/), shipped as
  `mini_app/assets/secure/admin-bundle.js`. The chunk is gated by
  [`SecureStaticMiddleware`](../../app/middlewares/secure_static.py)
  with an HMAC-signed `?t=...&u=<id>` URL produced by
  [`admin_manifest_service.sign_bundle_token`](../../app/services/admin_manifest_service.py).
- Auth: TOTP onboarding + device binding + admin JWT (15 min) +
  rotating refresh cookie + step-up TOTP for critical actions.

## Quick start (dev)

```bash
make admin-dev               # backend + infra
cd frontend && npm run dev   # frontend dev server (port 5173)

# optional but recommended: full observability stack
make observability-up        # prometheus, grafana, loki, tempo, cadvisor
```

Open `http://localhost:5173/{ADMIN_PANEL_PATH}` (after signing in to a regular
account that has `is_admin=true`). The first time it'll redirect to
the onboarding flow.

See [onboarding.md](onboarding.md) for the bootstrap of the very
first administrator from scratch.

## Observability (Prometheus / Loki)

- **Prometheus** (metrics in **Metrics**): set `PROMETHEUS_URL` in the
  backend `.env` to a reachable Prom base URL. With
  `docker-compose.observability.yml`, the host port is **9091** (mapped
  to Prom’s 9090), e.g. `PROMETHEUS_URL=http://localhost:9091` when the
  API runs on the host. The Prom config in `infra/prometheus/prometheus.yml`
  must scrape the same host:port as your running API (often
  `localhost:8000` in dev).
- **Loki** (log search in **Logs**): set `LOKI_URL` (e.g.
  `http://localhost:3100` with the observability compose).

## Local dev log files (no Docker Loki)

For `poetry run` on **Backend**, **Bot**, and **Compute worker** without
Loki, set a shared directory and the same env var in all three shells:

```bash
# Windows / PowerShell example
set DOTSOUND_DEV_LOG_DIR=C:\path\to\shared-logs
# or in backend .env:
DOTSOUND_DEV_LOG_DIR=C:\path\to\shared-logs
```

The API also reads `dotsound_dev_log_dir` from settings (same value).

- Backend mirrors console output to `backend.log` in that directory
  (see `app/core/logging.py`).
- Bot writes `bot.log` (`bot/core/logging.py` when `DOTSOUND_DEV_LOG_DIR` is set).
- Compute worker writes `compute-worker.log` (`worker/observability/log.py`).

With `loki_url` empty and `DOTSOUND_DEV_LOG_DIR` pointing at a real
directory, **Logs** in the admin UI uses **local_dev** mode (merged
tail of those files). **Live** log stream over the admin WebSocket uses
the same source when Loki is not configured.

## Admin sections

| Section | Route | Capability |
|---|---|---|
| Dashboard | `/{ADMIN_PANEL_PATH}` | – |
| Users | `/{ADMIN_PANEL_PATH}/users` | `users.manage` |
| Tracks | `/{ADMIN_PANEL_PATH}/tracks` | `tracks.manage` |
| Timecodes | `/{ADMIN_PANEL_PATH}/tracks/timecode-sync` | `tracks.manage` |
| Complaints | `/{ADMIN_PANEL_PATH}/complaints` | `complaints.moderate` |
| Artists | `/{ADMIN_PANEL_PATH}/artists` | `artists.enrich` |
| Compute | `/{ADMIN_PANEL_PATH}/audio-compute` | `audio_compute.manage` |
| Tasks | `/{ADMIN_PANEL_PATH}/tasks` | `tasks.manage` |
| Logs | `/{ADMIN_PANEL_PATH}/logs` | `logs.view` |
| Metrics | `/{ADMIN_PANEL_PATH}/metrics` | `metrics.view` |
| Containers | `/{ADMIN_PANEL_PATH}/containers` | `containers.view` |
| Audit | `/{ADMIN_PANEL_PATH}/audit` | `audit.view` |
| Security | `/{ADMIN_PANEL_PATH}/security` | `security.view` |
| Settings | `/{ADMIN_PANEL_PATH}/settings` | `settings.manage` |

Capabilities are stored per-user in the `admin_capabilities` table.
Even with `is_admin=true`, every menu item is invisible until a
matching capability is granted (see "Granting capabilities" below).

## Granting capabilities

A super-administrator (only known to `is_admin=true` + the
`settings.manage` capability) can grant capabilities through the
admin UI under **Users → user → Grant capability** (requires
step-up). For the very first admin, see
[onboarding.md](onboarding.md) for the SQL bootstrap.

The full list of known capabilities is exposed via
`GET /api/v1/{ADMIN_PANEL_PATH}/system/known-capabilities`.

## Step-up authentication

Sensitive actions (ban, role grants, feature flag toggles, audit
export, lockout release, etc.) require a fresh TOTP code beyond
the standard admin session. The frontend opens the `StepUpDialog`
automatically; the backend stores a Redis marker valid for 3-5
minutes (TTL controlled by PrivateCore).

The full list of "dangerous actions" lives in
`ADMIN_DANGEROUS_ACTIONS` inside
`dotsound_private_core.services.admin_security_policy`.

## Lockout

Five failed TOTP attempts within
`ADMIN_LOGIN_ATTEMPT_WINDOW_SECONDS` lock the account for
`ADMIN_LOCKOUT_TTL_SECONDS`. A super-admin with the
`security.release_lockout` capability can release it through
**Security → Locked admins → Release** (step-up required).

## Telegram alerts

Critical events fire alerts through Taskiq → DotSoundBot's
internal endpoint. See [security.md](security.md) for the contract
and the list of events.

## Lyrics timecode sync queue

Section **Timecodes** (`tracks/timecode-sync`, capability
`tracks.manage`) is for tracks that already have plain lyrics but no
synced timecodes. It enqueues `LyricsJob` rows tagged
`request_align_existing_text` and shows a dedicated queue: job in
progress, next waiting item, reorderable backlog, and recent
outcomes.

- **Start sync** tab: enqueue all eligible tracks (batch limit) or
  explicit track IDs. The tracks list filter «No timecodes» links here
  and supports batch enqueue for the current selection.
- **Queue** tab: optional filters **Only my enqueue runs** (matches
  `requested_by_user_id`) and **Last 24h / 7 days** (`since_hours`).
  Waiting jobs support numeric priority and **Run next** (bumps
  `queue_priority` above the current queued maximum). **Cancel** stops
  queued or running align jobs.
- REST: `GET/POST /tracks/lyrics-timecode-sync/queue|enqueue`,
  `PATCH .../jobs/{id}/priority`, `POST .../jobs/{id}/cancel`.
- On **Tasks → Lyrics jobs**, jobs with the align flag show the badge
  «Align existing text» (`request_align_existing_text`).

Background enqueue skips the catalog-only tier when aligning existing
text (same rule as manual user sync in `LyricsService`).

## Operations cheat sheet

```bash
# Health
curl http://localhost:8000/api/v1/health/deep | jq

# Show containers from CLI (matches what the panel renders)
curl -s http://localhost:8000/api/v1/{ADMIN_PANEL_PATH}/system/containers \
  -H "Authorization: Bearer $ADMIN_JWT" | jq

# Force re-build admin chunk only
cd frontend && npm run build:bundle-only

# Run backend tests
make test-admin
```

## Observability quick links

When the optional stack is up:

- Prometheus: <http://localhost:9091>
- Grafana: <http://localhost:3001> (admin/admin)
- Loki API: <http://localhost:3100>
- Tempo: <http://localhost:3200>
