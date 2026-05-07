/**
 * Worker table / drawer "status" is heartbeat liveness, not DB `active`.
 * Heartbeat defaults to every 15s on the worker; allow clock/network drift.
 */
import type { TFunction } from 'i18next'

export const WORKER_ONLINE_MAX_AGE_SEC = 60

export type WorkerLivenessReadout = {
  id: string
  active: boolean
  last_seen_at: string | null
  suspended_reason: string | null
  suspended_until: string | null
  revoked_at: string | null
  claims_paused_until?: string | null
}

export function suspendedNow(
  row: Pick<WorkerLivenessReadout, 'suspended_until'>,
): boolean {
  if (!row.suspended_until) {
    return false
  }
  return (
    new Date(
      row.suspended_until,
    ).getTime() > Date.now()
  )
}

export function claimsPausedNow(
  row: Pick<WorkerLivenessReadout, 'claims_paused_until'>,
): boolean {
  if (!row.claims_paused_until) {
    return false
  }
  return (
    new Date(
      row.claims_paused_until,
    ).getTime() > Date.now()
  )
}

function secondsSince(
  iso: string | null,
): number | null {
  if (!iso) {
    return null
  }
  const ts = Date.parse(iso)
  if (Number.isNaN(ts)) {
    return null
  }
  return (Date.now() - ts) / 1000
}

/**
 * For StatusPill colour: error (red), warn (no ping / old ping),
 * ok (recent heartbeat).
 */
export function computeWorkerPillKind(
  row: WorkerLivenessReadout,
): 'ok' | 'warn' | 'error' {
  if (row.revoked_at) {
    return 'error'
  }
  if (suspendedNow(row)) {
    return 'warn'
  }
  if (claimsPausedNow(row)) {
    return 'warn'
  }
  if (!row.active) {
    return 'error'
  }
  const age = secondsSince(
    row.last_seen_at,
  )
  if (age === null) {
    return 'warn'
  }
  if (age > WORKER_ONLINE_MAX_AGE_SEC) {
    return 'warn'
  }
  return 'ok'
}

/**
 * Translated one-line status for the pill + tables.
 */
export function computeWorkerPillLabel(
  row: WorkerLivenessReadout,
  t: TFunction,
  fmtUntil: (iso: string) => string = (iso) =>
    new Date(
      iso,
    ).toLocaleString(),
): string {
  const w = 'admin.audioCompute.workerState' as const
  if (row.revoked_at) {
    return t(`${w}.revoked`)
  }
  if (suspendedNow(row)) {
    const until = row.suspended_until
      ? fmtUntil(row.suspended_until)
      : '–'
    let s = t(`${w}.suspendedUntil`, {
      until,
    })
    const r = (row.suspended_reason || '')
      .trim()
    if (r) {
      s = `${s} · ${r}`
    }
    return s
  }
  if (claimsPausedNow(row)) {
    const until = row.claims_paused_until
      ? fmtUntil(row.claims_paused_until)
      : '–'
    return t(`${w}.claimsPausedUntil`, {
      until,
    })
  }
  if (!row.active) {
    return t(`${w}.accountDisabled`)
  }
  const age = secondsSince(
    row.last_seen_at,
  )
  if (age === null) {
    return t(`${w}.neverConnected`)
  }
  if (age > WORKER_ONLINE_MAX_AGE_SEC) {
    return t(`${w}.offline`, {
      sec: String(
        Math.floor(age),
      ),
    })
  }
  return t(`${w}.online`)
}
