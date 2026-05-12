import { isTelegram } from '@/lib/telegram'

export const DS_TG_BROWSER_HINT_LS = 'ds-tg-browser-hint'

export function isTelegramBrowserHintSuppressed(): boolean {
  if (!isTelegram()) return true
  try {
    const v = localStorage.getItem(DS_TG_BROWSER_HINT_LS)
    return v === 'perm' || v === 'tutorial'
  } catch {
    return true
  }
}

export function dismissTelegramBrowserHint(): void {
  try {
    localStorage.setItem(DS_TG_BROWSER_HINT_LS, 'perm')
  } catch {
    /* ignore */
  }
}

export function markTelegramBrowserHintTutorialSeen(): void {
  try {
    localStorage.setItem(DS_TG_BROWSER_HINT_LS, 'tutorial')
  } catch {
    /* ignore */
  }
}

export function buildMiniAppAbsoluteUrl(): string {
  const origin = window.location.origin
  const path = window.location.pathname || '/'
  const search = window.location.search || ''
  return `${origin}${path}${search}`
}
