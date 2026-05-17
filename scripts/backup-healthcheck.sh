#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/backups}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"
STATUS=0

log() { echo "[$(date -Iseconds)] HEALTH: $*"; }

latest=$(find "${BACKUP_ROOT}/daily" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -1)

if [ -z "${latest}" ]; then
    log "FAIL: no backups found in ${BACKUP_ROOT}/daily"
    exit 1
fi

log "Checking: ${latest}"

check_pg() {
    local encrypted="${latest}/pg_dump.custom.gpg"
    local plain="${latest}/pg_dump.custom"

    if [ -f "${encrypted}" ]; then
        if [ -z "${ENCRYPTION_KEY}" ]; then
            log "WARN: encrypted dump exists but no BACKUP_ENCRYPTION_KEY to verify"
            return
        fi
        local tmp
        tmp=$(mktemp)
        local key_file
        key_file=$(mktemp)
        printf '%s' "${ENCRYPTION_KEY}" > "${key_file}"
        if gpg --decrypt --batch --yes \
            --passphrase-file "${key_file}" \
            -o "${tmp}" "${encrypted}" 2>/dev/null; then
            if pg_restore --list "${tmp}" > /dev/null 2>&1; then
                local size
                size=$(stat -f%z "${encrypted}" 2>/dev/null || stat -c%s "${encrypted}")
                log "OK: PostgreSQL dump valid (${size} bytes, encrypted)"
            else
                log "FAIL: PostgreSQL dump corrupted (pg_restore --list failed)"
                STATUS=1
            fi
        else
            log "FAIL: PostgreSQL dump decryption failed"
            STATUS=1
        fi
        rm -f "${tmp}" "${key_file}"
    elif [ -f "${plain}" ]; then
        if pg_restore --list "${plain}" > /dev/null 2>&1; then
            local size
            size=$(stat -f%z "${plain}" 2>/dev/null || stat -c%s "${plain}")
            log "OK: PostgreSQL dump valid (${size} bytes)"
        else
            log "FAIL: PostgreSQL dump corrupted"
            STATUS=1
        fi
    else
        log "FAIL: no PostgreSQL dump found"
        STATUS=1
    fi
}

check_size_regression() {
    local previous
    previous=$(find "${BACKUP_ROOT}/daily" -mindepth 1 -maxdepth 1 -type d 2>/dev/null \
        | sort | tail -2 | head -1)

    if [ "${previous}" = "${latest}" ] || [ -z "${previous}" ]; then
        return
    fi

    local curr_size prev_size
    curr_size=$(du -sb "${latest}" | cut -f1)
    prev_size=$(du -sb "${previous}" | cut -f1)

    if [ "${prev_size}" -gt 0 ]; then
        local ratio
        ratio=$(( curr_size * 100 / prev_size ))
        if [ "${ratio}" -lt 50 ]; then
            log "WARN: backup size dropped to ${ratio}% of previous (${curr_size} vs ${prev_size})"
        else
            log "OK: size ratio ${ratio}% (current: ${curr_size}, previous: ${prev_size})"
        fi
    fi
}

check_redis() {
    if [ -f "${latest}/redis-dump.rdb" ]; then
        local size
        size=$(stat -f%z "${latest}/redis-dump.rdb" 2>/dev/null || stat -c%s "${latest}/redis-dump.rdb")
        log "OK: Redis RDB present (${size} bytes)"
    else
        log "INFO: no Redis RDB in this backup"
    fi
}

check_configs() {
    if [ -d "${latest}/configs" ]; then
        local count
        count=$(find "${latest}/configs" -type f | wc -l)
        log "OK: ${count} config file(s) saved"
    else
        log "INFO: no configs in this backup"
    fi
}

check_minio() {
    local minio_dir="${BACKUP_ROOT}/minio"
    local sentinel="${minio_dir}/.last_backup"

    if [ ! -d "${minio_dir}" ]; then
        log "WARN: MinIO mirror directory not found at ${minio_dir}"
        return
    fi

    if [ ! -f "${sentinel}" ]; then
        log "WARN: MinIO mirror exists but no .last_backup sentinel (never completed?)"
        return
    fi

    local age_seconds
    age_seconds=$(( $(date +%s) - $(stat -c%Y "${sentinel}" 2>/dev/null || \
        stat -f%m "${sentinel}" 2>/dev/null || echo 0) ))
    local age_hours=$(( age_seconds / 3600 ))

    if [ "${age_hours}" -gt 26 ]; then
        log "WARN: MinIO mirror stale — last backup ${age_hours}h ago"
    else
        local size
        size=$(du -sh "${minio_dir}" | cut -f1)
        log "OK: MinIO mirror present (${size}, ${age_hours}h ago)"
    fi
}

check_pg
check_size_regression
check_redis
check_configs
check_minio

if [ "${STATUS}" -eq 0 ]; then
    log "=== ALL CHECKS PASSED ==="
else
    log "=== SOME CHECKS FAILED ==="
fi

exit "${STATUS}"
