#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DAY_OF_WEEK=$(date +%u)
DAY_OF_MONTH=$(date +%d)
BACKUP_DIR="${BACKUP_ROOT}/daily/${TIMESTAMP}"

RETENTION_DAILY="${BACKUP_RETENTION_DAILY:-7}"
RETENTION_WEEKLY="${BACKUP_RETENTION_WEEKLY:-4}"
RETENTION_MONTHLY="${BACKUP_RETENTION_MONTHLY:-3}"

ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"
REMOTE_HOST="${BACKUP_REMOTE_HOST:-}"
REMOTE_PATH="${BACKUP_REMOTE_PATH:-/backups/dotsound}"
REMOTE_SSH_KEY="${BACKUP_REMOTE_SSH_KEY:-}"

MODE="${1:-full}"

log() { echo "[$(date -Iseconds)] $*"; }

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"

log "=== Backup started: mode=${MODE} dir=${BACKUP_DIR} ==="

backup_pg() {
    log "PostgreSQL: dumping..."
    local dump_file="${BACKUP_DIR}/pg_dump.custom"
    pg_dump \
        --format=custom \
        --compress=zstd:3 \
        --no-owner \
        --no-privileges \
        -f "${dump_file}"

    if [ -n "${ENCRYPTION_KEY}" ]; then
        log "PostgreSQL: encrypting..."
        local key_file
        key_file=$(mktemp)
        printf '%s' "${ENCRYPTION_KEY}" > "${key_file}"
        gpg --symmetric --batch --yes \
            --passphrase-file "${key_file}" \
            --cipher-algo AES256 \
            -o "${dump_file}.gpg" \
            "${dump_file}"
        rm -f "${dump_file}" "${key_file}"
        chmod 600 "${dump_file}.gpg"
        log "PostgreSQL: done (encrypted, $(du -sh "${dump_file}.gpg" | cut -f1))"
    else
        chmod 600 "${dump_file}"
        log "PostgreSQL: done (unencrypted, $(du -sh "${dump_file}" | cut -f1))"
    fi
}

backup_redis() {
    log "Redis: copying RDB snapshot..."
    local rdb_src="/redis-data/dump.rdb"
    if [ -f "${rdb_src}" ]; then
        cp "${rdb_src}" "${BACKUP_DIR}/redis-dump.rdb"
        chmod 600 "${BACKUP_DIR}/redis-dump.rdb"
        log "Redis: done ($(du -sh "${BACKUP_DIR}/redis-dump.rdb" | cut -f1))"
    else
        log "Redis: no RDB file found, skipping"
    fi
}

backup_configs() {
    log "Configs: copying..."
    local cfg_dir="${BACKUP_DIR}/configs"
    mkdir -p "${cfg_dir}"
    for f in /app/.env /app/docker-compose.yml; do
        if [ -f "${f}" ]; then
            cp "${f}" "${cfg_dir}/"
        fi
    done
    chmod -R 600 "${cfg_dir}"
    log "Configs: done"
}

backup_logs() {
    log "Logs: saving last 24h..."
    if command -v docker > /dev/null 2>&1; then
        docker compose logs --no-color --since 24h \
            > "${BACKUP_DIR}/docker-logs.txt" 2>/dev/null || true
    fi
    log "Logs: done"
}

rotate() {
    log "Rotation: cleaning old backups..."
    local dir="${BACKUP_ROOT}/daily"
    local count
    count=$(find "${dir}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    if [ "${count}" -gt "${RETENTION_DAILY}" ]; then
        find "${dir}" -mindepth 1 -maxdepth 1 -type d \
            | sort \
            | head -n "-${RETENTION_DAILY}" \
            | xargs rm -rf
        log "Rotation: daily trimmed to ${RETENTION_DAILY}"
    fi

    if [ "${DAY_OF_WEEK}" = "7" ]; then
        local weekly_dir="${BACKUP_ROOT}/weekly"
        mkdir -p "${weekly_dir}"
        cp -al "${BACKUP_DIR}" "${weekly_dir}/${TIMESTAMP}"
        local wcount
        wcount=$(find "${weekly_dir}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
        if [ "${wcount}" -gt "${RETENTION_WEEKLY}" ]; then
            find "${weekly_dir}" -mindepth 1 -maxdepth 1 -type d \
                | sort \
                | head -n "-${RETENTION_WEEKLY}" \
                | xargs rm -rf
        fi
        log "Rotation: weekly snapshot saved"
    fi

    if [ "${DAY_OF_MONTH}" = "01" ]; then
        local monthly_dir="${BACKUP_ROOT}/monthly"
        mkdir -p "${monthly_dir}"
        cp -al "${BACKUP_DIR}" "${monthly_dir}/${TIMESTAMP}"
        local mcount
        mcount=$(find "${monthly_dir}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
        if [ "${mcount}" -gt "${RETENTION_MONTHLY}" ]; then
            find "${monthly_dir}" -mindepth 1 -maxdepth 1 -type d \
                | sort \
                | head -n "-${RETENTION_MONTHLY}" \
                | xargs rm -rf
        fi
        log "Rotation: monthly snapshot saved"
    fi
}

sync_remote() {
    if [ -z "${REMOTE_HOST}" ]; then
        return
    fi
    log "Remote sync: rsync to ${REMOTE_HOST}..."
    local ssh_opts="ssh -o StrictHostKeyChecking=accept-new"
    if [ -n "${REMOTE_SSH_KEY}" ]; then
        ssh_opts="${ssh_opts} -i ${REMOTE_SSH_KEY}"
    fi
    rsync -azP --delete \
        -e "${ssh_opts}" \
        "${BACKUP_ROOT}/daily/" \
        "${BACKUP_ROOT}/weekly/" \
        "${BACKUP_ROOT}/monthly/" \
        "${REMOTE_HOST}:${REMOTE_PATH}/" || {
        log "Remote sync: FAILED"
        return 1
    }
    log "Remote sync: done"
}

backup_pg

if [ "${MODE}" = "full" ]; then
    backup_redis
    backup_configs
    backup_logs
fi

rotate
sync_remote || true

log "=== Backup completed: ${BACKUP_DIR} ==="

total_size=$(du -sh "${BACKUP_DIR}" | cut -f1)
log "Total size: ${total_size}"
