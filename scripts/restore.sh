#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${1:-}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"

if [ -z "${BACKUP_DIR}" ]; then
    echo "Usage: restore.sh <backup-directory>"
    echo "Example: restore.sh /backups/daily/20260413_030000"
    exit 1
fi

if [ ! -d "${BACKUP_DIR}" ]; then
    echo "ERROR: Directory not found: ${BACKUP_DIR}"
    exit 1
fi

log() { echo "[$(date -Iseconds)] $*"; }

log "=== Restore started from: ${BACKUP_DIR} ==="

read -rp "This will OVERWRITE current data. Continue? [y/N] " confirm
if [ "${confirm}" != "y" ] && [ "${confirm}" != "Y" ]; then
    log "Aborted by user"
    exit 0
fi

if [ -f "${BACKUP_DIR}/pg_dump.custom.gpg" ]; then
    log "PostgreSQL: decrypting..."
    if [ -z "${ENCRYPTION_KEY}" ]; then
        echo "ERROR: BACKUP_ENCRYPTION_KEY required for encrypted backup"
        exit 1
    fi
    key_file=$(mktemp)
    printf '%s' "${ENCRYPTION_KEY}" > "${key_file}"
    gpg --decrypt --batch --yes \
        --passphrase-file "${key_file}" \
        -o "${BACKUP_DIR}/pg_dump.custom" \
        "${BACKUP_DIR}/pg_dump.custom.gpg"
    rm -f "${key_file}"
    log "PostgreSQL: restoring..."
    pg_restore \
        --clean \
        --if-exists \
        --no-owner \
        --no-privileges \
        -d "${PGDATABASE:-dotsound}" \
        "${BACKUP_DIR}/pg_dump.custom"
    rm -f "${BACKUP_DIR}/pg_dump.custom"
    log "PostgreSQL: done (decrypted + restored)"
elif [ -f "${BACKUP_DIR}/pg_dump.custom" ]; then
    log "PostgreSQL: restoring (unencrypted)..."
    pg_restore \
        --clean \
        --if-exists \
        --no-owner \
        --no-privileges \
        -d "${PGDATABASE:-dotsound}" \
        "${BACKUP_DIR}/pg_dump.custom"
    log "PostgreSQL: done"
else
    log "PostgreSQL: no dump file found, skipping"
fi

if [ -f "${BACKUP_DIR}/redis-dump.rdb" ]; then
    log "Redis: copying RDB back..."
    local_rdb="/redis-data/dump.rdb"
    cp "${BACKUP_DIR}/redis-dump.rdb" "${local_rdb}"
    chmod 600 "${local_rdb}"
    log "Redis: done (restart Redis to apply)"
else
    log "Redis: no RDB file, skipping"
fi

if [ -d "${BACKUP_DIR}/configs" ]; then
    log "Configs: listing restored files..."
    ls -la "${BACKUP_DIR}/configs/"
    log "Configs: NOT auto-copied (review manually)"
fi

log "=== Restore completed ==="
log "Next steps:"
log "  1. Restart Redis: docker compose restart redis"
log "  2. Run migrations: poetry run alembic upgrade head"
log "  3. Verify data integrity"
