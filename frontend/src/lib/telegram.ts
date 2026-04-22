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
    return Boolean(
      (WebApp as any)?.initDataUnsafe?.user
        ?? (WebApp as any)?.platform,
    )
      && Boolean(window.Telegram?.WebApp)
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
    return localStorage.getItem(IS_ADMIN_KEY) === '1'
  } catch {
    return false
  }
}
