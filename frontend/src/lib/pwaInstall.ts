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

export function subscribePromptChange(
  fn: () => void,
): () => void {
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

// ── Platform detection ──────────────────────────────────

export function isStandalone(): boolean {
  try {
    return (
      window.matchMedia(
        '(display-mode: standalone)',
      ).matches ||
      (
        window.navigator as Navigator & {
          standalone?: boolean
        }
      ).standalone === true
    )
  } catch {
    return false
  }
}

export function isIOS(): boolean {
  try {
    const ua = navigator.userAgent || ''
    if (/iPad|iPhone|iPod/.test(ua)) return true
    if (
      /Mac/.test(navigator.platform) &&
      (
        (
          navigator as Navigator & {
            maxTouchPoints?: number
          }
        ).maxTouchPoints ?? 0
      ) > 1
    )
      return true
    return false
  } catch {
    return false
  }
}

export function isIOSSafari(): boolean {
  try {
    const ua = navigator.userAgent || ''
    if (!isIOS()) return false
    return (
      /Safari/.test(ua) &&
      !/CriOS|FxiOS|EdgiOS|OPiOS|OPT\//.test(ua)
    )
  } catch {
    return false
  }
}

export function isAndroid(): boolean {
  try {
    return /Android/.test(navigator.userAgent || '')
  } catch {
    return false
  }
}

export function isMobile(): boolean {
  return isIOS() || isAndroid()
}

export type Platform =
  | 'android-bip'
  | 'android-other'
  | 'ios-safari'
  | 'ios-other'

export function getPlatform(): Platform {
  if (isIOS()) {
    return isIOSSafari() ? 'ios-safari' : 'ios-other'
  }
  return hasDeferredPrompt()
    ? 'android-bip'
    : 'android-other'
}
