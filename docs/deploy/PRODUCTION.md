# DotSound — production deployment

This document describes how to bring a fresh server up to a working
production state and how the GitHub Actions auto-deploy chain works
afterwards.

> Hosting location: per `docs/legal/HOSTING.md` and 242-ФЗ, the
> production server with PD storage must be located inside RF.

## 1. Server prerequisites

Tested on Ubuntu 22.04+. Required on the host:

- Docker Engine 24+ and Docker Compose v2 (`docker compose`).
- Open inbound TCP ports `22`, `80`, `443` (UDP `443` for HTTP/3).
- All other compose services stay on the internal `dotsound`
  Docker network — never expose Postgres/Redis/MinIO/ES to the
  public internet.
- DNS A-record for the main domain pointing at the host's public IP.
- (Optional but recommended) DNS A-record for the MinIO subdomain
  (e.g. `media.your-domain.com`) — see §6.

## 2. Filesystem layout

```
/opt/dotsound/
├── DotSoundBackend/           # this repo
├── DotSoundBot/
├── DotSoundPrivateCore/
└── DotSoundComputeWorker/     # optional; not deployed on the API host by default
```

Clone all four repos as the same Unix user that will run docker
(typically `root` or a dedicated `dotsound` user with docker group).

```
sudo mkdir -p /opt/dotsound
sudo chown $USER:$USER /opt/dotsound
cd /opt/dotsound
git clone https://github.com/<org>/DotSoundBackend.git
git clone https://github.com/<org>/DotSoundBot.git
git clone https://github.com/<org>/DotSoundPrivateCore.git
```

## 3. Required `.env` files

Each repo has its own `.env.example`. Copy and fill them:

| File | What goes inside |
| --- | --- |
| `DotSoundBackend/.env` | DB / Redis / MinIO / Elasticsearch / `JWT_SECRET` / `ADMIN_JWT_SECRET` / `ADMIN_CSRF_SECRET` / `TOTP_ENCRYPTION_KEY` / `CHAT_ENCRYPTION_KEY` / `RESEND_API_KEY` / `BACKUP_ENCRYPTION_KEY` / `TELEGRAM_BOT_TOKEN` / `MINI_APP_URL` / `ALLOWED_ORIGINS` / `DOMAIN` / `ACME_EMAIL` / **`BOT_INTERNAL_URL=http://bot:8081`** when Backend and Bot share Compose (not `localhost`) / matching `BOT_INTERNAL_SECRET` |
| `DotSoundBackend/.env` | **For production: set `DEBUG=false`.** |
| `DotSoundBot/.env` | `BOT_TOKEN` / `BACKEND_BASE_URL=http://backend:8000` / `INTERNAL_API_SECRET` (must match `BOT_INTERNAL_SECRET` in Backend `.env`) / `MINI_APP_URL` / in Compose, `docker-compose.yml` sets **`INTERNAL_API_COMPOSE_BIND=true`** and **`INTERNAL_API_HOST=0.0.0.0`** (do not publish port 8081 on the host). |
| `DotSoundPrivateCore/.env` | PrivateCore-only configuration (lyrics provider tokens, audio-stage settings, Whisper config, Yandex Cloud keys, optional `OUTBOUND_*` Tor/proxy knobs for Yandex/VK import). The Backend never reads or echoes these variables. |

For remote compute workers, set `INTERNAL_API_ALLOWED_CIDRS` in
`DotSoundBackend/.env` to the workers' egress CIDRs. If Backend is
reached through Caddy/nginx in Compose, keep `TRUSTED_PROXY_CIDRS`
covering the proxy container subnet or set `INTERNAL_API_TRUSTED_PROXIES`
explicitly; otherwise `/api/v1/internal/*` will see the Docker peer IP
and return masked `404` responses.
The compose file appends `172.16.0.0/12` for local compose workers.

Generation helpers for the cryptographic values:

```
python -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"   # TOTP / chat encryption keys
python -c "import secrets;print(secrets.token_urlsafe(64))"                     # ADMIN_JWT_SECRET
python -c "import secrets;print(secrets.token_urlsafe(32))"                     # ADMIN_CSRF_SECRET / BACKUP_ENCRYPTION_KEY
```

Caddy reads `DOMAIN` and `ACME_EMAIL` from `DotSoundBackend/.env`
via `docker-compose.prod.yml`.

> **Secrets are out of scope for the AI agent.** All `.env` files
> must be created by a human operator; the agent is forbidden from
> reading or writing them (see `.cursor/rules/secrets-and-env.mdc`).

## 4. First production boot

From the Backend repo on the server:

```
cd /opt/dotsound/DotSoundBackend
./scripts/deploy.sh full
```

What `deploy.sh full` does:

1. `git pull` for each sibling repo.
2. `docker compose build` against `docker-compose.yml` overlaid by
   `docker-compose.prod.yml`.
3. Brings up Postgres / Redis / MinIO / Elasticsearch and waits for
   Postgres `pg_isready`.
4. Runs `alembic upgrade head` inside a one-shot backend container.
5. Starts `backend`, `worker`, `frontend`, `caddy`, `bot`.
6. Prunes dangling images.

After the first boot:

- MinIO bucket bootstrap is handled by Backend (`ensure_bucket_exists`)
  on lifespan startup.
- Caddy provisions Let's Encrypt certificates automatically on first
  request (`DOMAIN` must already resolve to this host).
- Healthchecks: `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps`.

## 5. GitHub Actions auto-deploy

Three workflows are configured (one per repo). All trigger on
`push: main` and call the same `scripts/deploy.sh` on the server:

| Repo | Mode | Rebuilds |
| --- | --- | --- |
| `DotSoundBackend` | `only-backend` | `backend`, `worker` (and migrations) |
| `DotSoundBot` | `only-bot` | `bot` |
| `DotSoundPrivateCore` | `full` | everything that imports PrivateCore (backend + worker + bot) |

### Required GitHub secrets (in EACH of the three repos)

| Secret | Value |
| --- | --- |
| `SERVER_HOST` | Public IP or hostname |
| `SERVER_USER` | Unix user that owns `/opt/dotsound` and is in the `docker` group |
| `SSH_PRIVATE_KEY` | Private key whose public half is in `~/.ssh/authorized_keys` on the server |
| `SERVER_SSH_PORT` | (Optional) Non-default SSH port |

### What the script does NOT do

- It does not write `.env` files. Provision them out of band.
- It does not roll back automatically on failed migrations — Alembic
  failures abort deploy with a non-zero exit; the previously running
  containers stay live.

## 6. MinIO public subdomain (presigned URLs)

Backend issues presigned S3 URLs pointing at `MINIO_ENDPOINT`. Inside
Docker that's `minio:9000`, which the browser cannot reach. For
end-user audio/cover playback you need MinIO reachable over a public
HTTPS endpoint.

Steps:

1. Add an A record `media.your-domain.com` pointing at the same host.
2. In `Caddyfile`, uncomment the `media.your-domain.com` block and
   replace the placeholder with your subdomain.
3. In `DotSoundBackend/.env`:
   ```
   MINIO_ENDPOINT=media.your-domain.com
   MINIO_USE_SSL=true
   ```
4. Re-run `./scripts/deploy.sh skip-pull`.

If your closed beta runs on private IPs only, you may skip this and
proxy audio through the Backend HLS routes instead, but the default
playback path uses presigned URLs.

## 7. Smoke test

```
curl -fsS https://your-domain.com/api/v1/health         # backend health
curl -fsS https://your-domain.com/                       # 301 -> /mini_app/
curl -fsSI https://your-domain.com/mini_app/             # 200 + Cache-Control
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50 caddy
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50 bot
```

In Telegram, send `/start` to the bot. The Mini App button should
open at `https://your-domain.com/mini_app/`.

## 8. Operational notes

- Compose overlay file `docker-compose.prod.yml` removes
  `ports:` and bind-mount `volumes:` that exist in
  `docker-compose.yml` for dev. Internal services are only reachable
  on the `dotsound` Docker network.
- `DEBUG=false` is enforced by `docker-compose.prod.yml`. If you
  override it in `.env`, the compose env still wins.
- ClamAV (`UPLOAD_MALWARE_SCAN_MODE=clamav`) requires 4+ GB RAM. On
  smaller VPS use `lightweight`.
- Database and object-storage backups run automatically:
  `docker-compose.prod.yml` removes the `backup` profile so the container
  starts with the rest of the stack on every `./scripts/deploy.sh`
  invocation. No manual `--profile backup` needed in production.
  The backup container uses a custom image (`docker/Dockerfile.backup`)
  that includes PostgreSQL client tools, `mc` (MinIO client), `gnupg`,
  and `rsync`.
  Cron schedule (UTC):
  - `0 */6 * * *` — PostgreSQL-only dump every 6 hours.
  - `0 3 * * *` — full backup (PostgreSQL + Redis + MinIO mirror +
    configs + logs).
  - `0 4 * * *` — healthcheck on the latest backup.
  MinIO audio files are mirrored incrementally to `/backups/minio/` and
  included in the remote rsync when `BACKUP_REMOTE_HOST` is set.
  Configure in `.env`:
  `BACKUP_ENCRYPTION_KEY`, `BACKUP_RETENTION_*`,
  `BACKUP_REMOTE_HOST`, `BACKUP_REMOTE_SSH_KEY`, `MINIO_BACKUP_ENDPOINT`.
- Compute worker (`compute-worker-cpu` / `compute-worker-gpu`) lives
  behind profiles. The default deploy does **not** start it; see the
  ComputeWorker README to run it on a dedicated host.
