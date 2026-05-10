export interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

let _deferred: BeforeInstallPromptEvent | null = null
const _subs = new Set<() => void>()

export function captureBeforeInstallPrompt(): void {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    _deferred = e as BeforeInstallPromptEvent
    _subs.forEach((fn) => fn())
  })
  window.addEventListener('appinstalled', () => {
    _deferred = null
    _subs.forEach((fn) => fn())
  })
}

export function hasDeferredPrompt(): boolean {
  return _deferred !== null
}

export function subscribePromptChange(fn: () => void): () => void {
  _subs.add(fn)
  return () => {
    _subs.delete(fn)
  }
}

export async function triggerPwaInstall(): Promise<
  'accepted' | 'dismissed' | null
> {
  if (!_deferred) return null
  const d = _deferred
  _deferred = null
  _subs.forEach((fn) => fn())
  await d.prompt()
  const { outcome } = await d.userChoice
  return outcome
}
