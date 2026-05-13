const PENDING_ID_KEY = 'admin_device_pending_id'
const FLOW_EPOCH_KEY = 'admin_device_flow_epoch'
const AUTO_SENT_EPOCH_KEY = 'admin_device_auto_sent_epoch'

function safeGet(key: string): string {
  try {
    return sessionStorage.getItem(key) ?? ''
  } catch {
    return ''
  }
}

function safeSet(key: string, value: string): void {
  try {
    sessionStorage.setItem(key, value)
  } catch {
    /* private mode / quota */
  }
}

function safeRemove(key: string): void {
  try {
    sessionStorage.removeItem(key)
  } catch {
    /* ignore */
  }
}

export function persistPendingDeviceId(id: number): void {
  safeSet(PENDING_ID_KEY, String(id))
}

export function readPendingDeviceId(): number | null {
  const raw = safeGet(PENDING_ID_KEY).trim()
  if (!raw) return null
  const n = Number.parseInt(raw, 10)
  return Number.isFinite(n) && n > 0 ? n : null
}

export function beginDeviceApprovalFlow(): void {
  safeSet(FLOW_EPOCH_KEY, String(Date.now()))
}

export function getFlowEpoch(): string {
  return safeGet(FLOW_EPOCH_KEY)
}

export function getLastAutoSentFlowEpoch(): string {
  return safeGet(AUTO_SENT_EPOCH_KEY)
}

export function markAutoApprovalSentForCurrentFlow(): void {
  safeSet(AUTO_SENT_EPOCH_KEY, getFlowEpoch())
}

export function clearDeviceApprovalBrowserState(): void {
  safeRemove(PENDING_ID_KEY)
  safeRemove(FLOW_EPOCH_KEY)
  safeRemove(AUTO_SENT_EPOCH_KEY)
}
