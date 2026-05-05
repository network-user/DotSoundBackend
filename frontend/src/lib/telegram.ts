import WebApp from '@twa-dev/sdk'

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData?: string
        initDataUnsafe?: { user?: { id?: number } }
      }
    }
  }
}

WebApp.ready()
WebApp.expand()

export const tg = WebApp

type HapticImpact = 'light' | 'medium' | 'heavy'

/**
 * No-op kept for backwards compatibility.
 *
 * The original implementation copied Telegram theme parameters
 * onto the document and toggled a `tg-theme-on` class so CSS
 * could re-derive its palette from the running Telegram theme.
 * That broke the deterministic monochrome design (e.g. blue
 * accents in the default Telegram theme), so the palette is now
 * fixed in `global.css` and this bridge intentionally does
 * nothing. The function is kept exported so existing imports
 * stay valid.
 */
export function installTelegramThemeBridge(): void {
  /* deliberately no-op — see docstring */
}

export function installViewportListener(): void {
  const update = () => {
    try {
      const h =
        (WebApp as any).viewportStableHeight ||
        window.innerHeight
      document.documentElement.style.setProperty(
        '--vh',
        `${h * 0.01}px`,
      )
    } catch {
      /* ignore */
    }
  }
  update()
  try {
    ;(WebApp as any).onEvent?.(
      'viewportChanged',
      update,
    )
  } catch {
    /* ignore */
  }
  window.addEventListener('resize', update)
}

export function setBackButton(
  visible: boolean,
  onClick?: () => void,
): () => void {
  try {
    const bb = (WebApp as any).BackButton
    if (!bb) return () => undefined
    if (visible && onClick) {
      bb.onClick(onClick)
      bb.show()
      return () => {
        try {
          bb.offClick(onClick)
          bb.hide()
        } catch {
          /* ignore */
        }
      }
    }
    bb.hide()
  } catch {
    /* ignore */
  }
  return () => undefined
}

export function isTelegram(): boolean {
  try {
    const init = (WebApp as any)?.initData
    if (typeof init === 'string' && init.length > 0) {
      return true
    }
    const u = (WebApp as any)?.initDataUnsafe?.user
    return (
      u !== undefined
      && u !== null
      && typeof u === 'object'
    )
  } catch {
    return false
  }
}

const VIBRATE_MAP: Record<HapticImpact, number> = {
  light: 10,
  medium: 18,
  heavy: 28,
}

const VIBRATE_NOTIF: Record<
  'success' | 'warning' | 'error',
  number | number[]
> = {
  success: [10, 30, 10],
  warning: [20, 40, 20],
  error: [40, 30, 40],
}

export function haptic(
  kind: HapticImpact = 'light',
): void {
  try {
    const tgHaptic = (WebApp as any).HapticFeedback
    if (tgHaptic?.impactOccurred) {
      tgHaptic.impactOccurred(kind)
      return
    }
  } catch {
    /* fall through to navigator.vibrate */
  }
  try {
    if ('vibrate' in navigator) {
      navigator.vibrate(VIBRATE_MAP[kind])
    }
  } catch {
    /* ignore */
  }
}

export function hapticNotification(
  kind: 'success' | 'warning' | 'error',
): void {
  try {
    const tgHaptic = (WebApp as any).HapticFeedback
    if (tgHaptic?.notificationOccurred) {
      tgHaptic.notificationOccurred(kind)
      return
    }
  } catch {
    /* fall through to navigator.vibrate */
  }
  try {
    if ('vibrate' in navigator) {
      navigator.vibrate(VIBRATE_NOTIF[kind])
    }
  } catch {
    /* ignore */
  }
}

export function hapticSelection(): void {
  try {
    const tgHaptic = (WebApp as any).HapticFeedback
    if (tgHaptic?.selectionChanged) {
      tgHaptic.selectionChanged()
      return
    }
  } catch {
    /* fall through */
  }
  try {
    if ('vibrate' in navigator) {
      navigator.vibrate(5)
    }
  } catch {
    /* ignore */
  }
}

function nativeInitData(): string {
  try {
    return window.Telegram?.WebApp?.initData ?? ''
  } catch {
    return ''
  }
}

export function getInitData(): string {
  return tg.initData || nativeInitData()
}

export const telegramId: number | null =
  WebApp.initDataUnsafe?.user?.id
  ?? window.Telegram?.WebApp?.initDataUnsafe?.user?.id
  ?? null

const INTERNAL_USER_ID_KEY =
  'auth-user-id'

function loadStoredInternalUserId():
  | number
  | null {
  try {
    const raw = localStorage.getItem(
      INTERNAL_USER_ID_KEY,
    )
    if (!raw) return null
    const parsed = Number(raw)
    return Number.isFinite(parsed)
      ? parsed
      : null
  } catch {
    return null
  }
}

let _internalUserId: number | null =
  loadStoredInternalUserId()

export function setInternalUserId(
  id: number | null,
): void {
  _internalUserId = id
  try {
    if (id === null) {
      localStorage.removeItem(
        INTERNAL_USER_ID_KEY,
      )
    } else {
      localStorage.setItem(
        INTERNAL_USER_ID_KEY,
        String(id),
      )
    }
  } catch {}
}

export function getInternalUserId():
  | number
  | null {
  return _internalUserId
}

export function getUserId(): number | null {
  return _internalUserId
}

const IS_ADMIN_KEY = 'auth-is-admin'
const AUTH_TOKEN_KEY = 'auth-token'

export function setIsAdmin(value: boolean): void {
  try {
    if (value) {
      localStorage.setItem(IS_ADMIN_KEY, '1')
    } else {
      localStorage.removeItem(IS_ADMIN_KEY)
    }
  } catch {}
}

export function getIsAdmin(): boolean {
  try {
    if (localStorage.getItem(IS_ADMIN_KEY) === '1') {
      return true
    }
    const token = localStorage.getItem(AUTH_TOKEN_KEY)
    if (!token) return false
    const parts = token.split('.')
    if (parts.length < 2) return false
    const payloadBase64 = parts[1]
      .replace(/-/g, '+')
      .replace(/_/g, '/')
    const padded = payloadBase64.padEnd(
      payloadBase64.length +
        ((4 - (payloadBase64.length % 4)) % 4),
      '=',
    )
    const payloadRaw = atob(padded)
    const payload = JSON.parse(payloadRaw) as Record<string, unknown>
    return payload.is_admin === true
  } catch {
    return false
  }
}
