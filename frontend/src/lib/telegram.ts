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
