#!/usr/bin/env bash
# DotSound — production deploy script.
#
# Idempotent: safe to re-run. Pulls latest sibling-repo code, rebuilds
# changed images, runs Alembic migrations against the live database,
# then rolls all app services. Postgres / Redis / MinIO / Elasticsearch
# are NOT recreated unless their compose definition changed. The
# sc_id_refresher sidecar (SoundCloud client_id → .env weekly) is
# started with backend/worker on prod (see docker-compose.prod.yml).
#
# Layout expected on the server:
#   /opt/dotsound/DotSoundBackend       (this repo, cwd)
#   /opt/dotsound/DotSoundBot
#   /opt/dotsound/DotSoundPrivateCore
#   /opt/dotsound/DotSoundComputeWorker  (optional)
#
# Usage:
#   cd /opt/dotsound/DotSoundBackend
#   ./scripts/deploy.sh                # full deploy (default)
#   ./scripts/deploy.sh skip-pull      # rebuild + migrate, no git pull
#   ./scripts/deploy.sh only-backend   # rebuild only backend+worker
#   ./scripts/deploy.sh only-bot       # rebuild only bot
#   ./scripts/deploy.sh only-frontend  # rebuild only frontend+caddy
#
# Optional observability stack (Prometheus / Loki / Tempo / Grafana /
# Promtail / OTEL collector / cAdvisor):
#   OBSERVABILITY=1 ./scripts/deploy.sh full
#   OBSERVABILITY=1 ./scripts/deploy.sh skip-pull

set -euo pipefail

MODE="${1:-full}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PARENT_DIR="$(cd "${REPO_ROOT}/.." && pwd)"

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.prod.yml)

# Optional observability stack (Prometheus / Loki / Tempo / Grafana /
# Promtail / OTEL / cAdvisor). Enable by exporting OBSERVABILITY=1
# before invoking this script:
#   OBSERVABILITY=1 ./scripts/deploy.sh full
if [ "${OBSERVABILITY:-0}" = "1" ]; then
  COMPOSE_FILES+=(-f docker-compose.observability.yml)
  COMPOSE_FILES+=(-f docker-compose.observability.prod.yml)
fi

COMPOSE=(docker compose "${COMPOSE_FILES[@]}")
DEPLOY_PRUNE_BUILDER_CACHE="${DEPLOY_PRUNE_BUILDER_CACHE:-1}"
# Soft cache keep only when the host has headroom. On the 3.8GB/small-disk
# prod box a retained BuildKit cache collides with apt/image layers and
# fails with: E: not enough free space in /var/cache/apt/archives/.
# Override via env on larger hosts (e.g. DEPLOY_BUILDER_CACHE_KEEP_STORAGE=12GB).
DEPLOY_BUILDER_CACHE_KEEP_STORAGE="${DEPLOY_BUILDER_CACHE_KEEP_STORAGE:-2GB}"
# Below this free space (MiB) we hard-prune builder cache + unused images.
DEPLOY_MIN_FREE_MIB="${DEPLOY_MIN_FREE_MIB:-2048}"
# Absolute floor: refuse to start a build if still this low after prune.
DEPLOY_BUILD_FLOOR_MIB="${DEPLOY_BUILD_FLOOR_MIB:-900}"

log() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

free_mib() {
  # Portable free space on / (Linux deploy host). Empty on failure.
  df -Pm / 2>/dev/null | awk 'NR==2 {print $4}'
}

# Free Docker disk before image builds. Soft prune first; if free space is
# still below DEPLOY_MIN_FREE_MIB, drop builder cache entirely and unused
# images (running stack images stay). Fail fast if still below floor.
free_build_disk() {
  log "Pre-build disk cleanup"
  docker container prune -f >/dev/null 2>&1 || true
  docker image prune -f >/dev/null 2>&1 || true
  if [ "${DEPLOY_PRUNE_BUILDER_CACHE}" = "1" ]; then
    docker builder prune -af \
      --keep-storage "${DEPLOY_BUILDER_CACHE_KEEP_STORAGE}" \
      >/dev/null 2>&1 || true
  fi

  local free
  free="$(free_mib || true)"
  if [ -n "${free}" ] && [ "${free}" -lt "${DEPLOY_MIN_FREE_MIB}" ]; then
    log "Low disk (${free} MiB free < ${DEPLOY_MIN_FREE_MIB}) - hard prune"
    docker builder prune -af >/dev/null 2>&1 || true
    docker image prune -af >/dev/null 2>&1 || true
    docker system prune -af >/dev/null 2>&1 || true
    free="$(free_mib || true)"
  fi

  log "Disk after cleanup:"
  df -h / /var/lib/docker 2>/dev/null | sed 's/^/    /' || true
  docker system df 2>/dev/null | sed 's/^/    /' || true

  if [ -n "${free}" ] && [ "${free}" -lt "${DEPLOY_BUILD_FLOOR_MIB}" ]; then
    echo "ERROR: only ${free} MiB free on /; need >= ${DEPLOY_BUILD_FLOOR_MIB} MiB to build images." >&2
    echo "Free space on the server (docker system prune, remove old images/logs), then re-run." >&2
    exit 1
  fi
}

# Build images one at a time. On a small build host, building every image in
# parallel thrashes disk IO - that's what dragged apt to ~48 min and tripped
# esbuild's postinstall with ETXTBSY. Serialising costs a little wall-clock on
# a cold cache but is stable; with the build cache retained between deploys
# each image is mostly cache hits anyway.
build_serial() {
  free_build_disk
  for svc in "$@"; do
    log "Building ${svc}"
    "${COMPOSE[@]}" build "${svc}"
  done
}

# Frontend image is built by CI and pushed to GHCR (see
# .github/workflows/deploy.yml) so this box never runs the RAM-heavy
# vite build that used to OOM here. Pull it; if the pull fails (image
# not published/public yet, or GHCR_OWNER wrong), fall back to an
# on-server build so a deploy never hard-breaks on the registry.
deploy_frontend() {
  log "Pulling frontend image from registry"
  if "${COMPOSE[@]}" pull frontend; then
    log "Frontend image pulled"
  else
    log "Frontend pull failed - building on server (fallback)"
    "${COMPOSE[@]}" build frontend
  fi
}

# Buildable services active in the prod stack (postgres/redis/minio/
# elasticsearch/clamav/caddy are pulled images, not built). backend, worker
# and sc_id_refresher share one image, so the 2nd/3rd are cache hits.
# frontend is intentionally absent: its image is pulled from GHCR (see
# deploy_frontend), not built on this box.
BUILD_SERVICES=(backend worker bot sc_id_refresher backup)

pull_repo() {
  local name="$1"
  local path="${PARENT_DIR}/${name}"
  if [ ! -d "${path}/.git" ]; then
    log "Skip git pull: ${path} is not a git checkout"
    return 0
  fi
  log "git pull ${name}"
  git -C "${path}" fetch --prune origin main
  git -C "${path}" reset --hard origin/main
}

wait_for_postgres() {
  log "Waiting for postgres to become healthy"
  for i in $(seq 1 60); do
    if "${COMPOSE[@]}" exec -T postgres pg_isready -U "${POSTGRES_USER:-dotsound}" >/dev/null 2>&1; then
      log "Postgres ready"
      return 0
    fi
    sleep 2
  done
  echo "Postgres did not become ready in 120s" >&2
  exit 1
}

run_migrations() {
  log "Running alembic upgrade head"
  "${COMPOSE[@]}" run --rm backend alembic upgrade head
}

cd "${REPO_ROOT}"

case "${MODE}" in
  full)
    pull_repo DotSoundBackend
    pull_repo DotSoundBot
    pull_repo DotSoundPrivateCore
    pull_repo DotSoundComputeWorker || true

    log "Building images"
    build_serial "${BUILD_SERVICES[@]}"
    deploy_frontend

    log "Bringing up infrastructure (postgres/redis/minio/elasticsearch)"
    "${COMPOSE[@]}" up -d postgres redis minio elasticsearch
    wait_for_postgres

    run_migrations

    log "Rolling app services"
    "${COMPOSE[@]}" up -d \
      backend worker frontend caddy bot sc_id_refresher backup
    if [ "${OBSERVABILITY:-0}" = "1" ]; then
      log "Starting observability stack"
      "${COMPOSE[@]}" up -d \
        prometheus loki promtail tempo otel-collector cadvisor grafana
    fi
    ;;

  skip-pull)
    log "Building images"
    build_serial "${BUILD_SERVICES[@]}"
    deploy_frontend
    "${COMPOSE[@]}" up -d postgres redis minio elasticsearch
    wait_for_postgres
    run_migrations
    "${COMPOSE[@]}" up -d \
      backend worker frontend caddy bot sc_id_refresher backup
    if [ "${OBSERVABILITY:-0}" = "1" ]; then
      log "Starting observability stack"
      "${COMPOSE[@]}" up -d \
        prometheus loki promtail tempo otel-collector cadvisor grafana
    fi
    ;;

  only-backend)
    pull_repo DotSoundBackend
    pull_repo DotSoundPrivateCore
    build_serial backend worker sc_id_refresher
    "${COMPOSE[@]}" up -d postgres redis minio elasticsearch
    wait_for_postgres
    run_migrations
    "${COMPOSE[@]}" up -d backend worker sc_id_refresher backup
    ;;

  only-bot)
    pull_repo DotSoundBot
    pull_repo DotSoundPrivateCore
    build_serial bot
    "${COMPOSE[@]}" up -d bot
    ;;

  only-frontend)
    pull_repo DotSoundBackend
    deploy_frontend
    "${COMPOSE[@]}" up -d frontend caddy
    ;;

  *)
    echo "Unknown mode: ${MODE}" >&2
    echo "Usage: $0 [full|skip-pull|only-backend|only-bot|only-frontend]" >&2
    exit 2
    ;;
esac

log "Pruning dangling images"
docker image prune -f >/dev/null

if [ "${DEPLOY_PRUNE_BUILDER_CACHE}" = "1" ]; then
  log "Pruning Docker build cache"
  docker builder prune -af \
    --keep-storage "${DEPLOY_BUILDER_CACHE_KEEP_STORAGE}" \
    >/dev/null
fi

log "Done"
