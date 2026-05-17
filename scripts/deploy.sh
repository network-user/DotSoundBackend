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
DEPLOY_BUILDER_CACHE_KEEP_STORAGE="${DEPLOY_BUILDER_CACHE_KEEP_STORAGE:-4GB}"

log() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

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
    "${COMPOSE[@]}" build

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
    "${COMPOSE[@]}" build
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
    "${COMPOSE[@]}" build backend worker sc_id_refresher
    "${COMPOSE[@]}" up -d postgres redis minio elasticsearch
    wait_for_postgres
    run_migrations
    "${COMPOSE[@]}" up -d backend worker sc_id_refresher backup
    ;;

  only-bot)
    pull_repo DotSoundBot
    pull_repo DotSoundPrivateCore
    "${COMPOSE[@]}" build bot
    "${COMPOSE[@]}" up -d bot
    ;;

  only-frontend)
    pull_repo DotSoundBackend
    "${COMPOSE[@]}" build frontend
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
