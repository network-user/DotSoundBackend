const RECOVERY_KEY = 'ds:stale-build-recovery-at'
const RECOVERY_WINDOW_MS = 60_000

function messageFrom(value: unknown): string {
  if (value instanceof Error) return value.message
  if (typeof value === 'string') return value
  if (typeof value !== 'object' || value === null) return ''
  const record = value as Record<string, unknown>
  if (record.type === 'vite:preloadError') {
    return 'Failed to fetch dynamically imported module'
  }
  const message = record.message
  if (typeof message === 'string') return message
  const reason = record.reason
  if (reason instanceof Error) return reason.message
  if (typeof reason === 'string') return reason
  const payload = messageFrom(record.payload)
  if (payload) return payload
  const detail = messageFrom(record.detail)
  if (detail) return detail
  return ''
}

export function isStaleBuildError(value: unknown): boolean {
  const text = messageFrom(value)
  return (
    text.includes('does not provide an export named') ||
    text.includes('Failed to fetch dynamically imported module') ||
    text.includes('error loading dynamically imported module') ||
    text.includes('Importing a module script failed') ||
    text.includes('ChunkLoadError')
  )
}

export function recoverFromStaleBuild(value: unknown): void {
  if (!isStaleBuildError(value)) return
  try {
    const now = Date.now()
    const previous = Number(
      window.sessionStorage.getItem(RECOVERY_KEY) || '0',
    )
    if (
      Number.isFinite(previous) &&
      now - previous < RECOVERY_WINDOW_MS
    ) {
      return
    }
    window.sessionStorage.setItem(RECOVERY_KEY, String(now))
  } catch {
    return
  }

  const cleanup: Promise<unknown>[] = []
  if ('serviceWorker' in navigator) {
    cleanup.push(
      navigator.serviceWorker
        .getRegistrations()
        .then((registrations) =>
          Promise.all(
            registrations.map((registration) =>
              registration.unregister(),
            ),
          ),
        ),
    )
  }
  if ('caches' in window) {
    cleanup.push(
      window.caches.keys().then((names) =>
        Promise.all(
          names
            .filter(
              (name) =>
                name.includes('mini-app') ||
                name.includes('workbox'),
            )
            .map((name) => window.caches.delete(name)),
        ),
      ),
    )
  }

  void Promise.allSettled(cleanup).finally(() => {
    const url = new URL(window.location.href)
    url.searchParams.set('nosw', '1')
    url.searchParams.set('v', String(Date.now()))
    window.location.replace(url.toString())
  })
}
