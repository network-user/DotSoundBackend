import { tg } from '@/lib/telegram'

export type Platform = 'telegram' | 'web'
export type FormFactor = 'mobile' | 'tablet' | 'desktop'

const MOBILE_MAX = 480
const TABLET_MAX = 1024

export function isTelegramMiniApp(): boolean {
  try {
    const w = window as unknown as {
      Telegram?: { WebApp?: { initData?: string } }
    }
    const hasInitData = Boolean(
      tg?.initData?.length || w.Telegram?.WebApp?.initData,
    )
    const hasUser = Boolean(tg?.initDataUnsafe?.user?.id)
    return hasInitData || hasUser
  } catch {
    return false
  }
}

export function isWebApp(): boolean {
  return !isTelegramMiniApp()
}

export function getPlatform(): Platform {
  return isTelegramMiniApp() ? 'telegram' : 'web'
}

export function getFormFactor(): FormFactor {
  if (typeof window === 'undefined') return 'desktop'
  const w = window.innerWidth
  if (w <= MOBILE_MAX) return 'mobile'
  if (w <= TABLET_MAX) return 'tablet'
  return 'desktop'
}

export function isTouchDevice(): boolean {
  if (typeof window === 'undefined') return false
  return (
    'ontouchstart' in window ||
    (navigator.maxTouchPoints ?? 0) > 0
  )
}

export interface ShareCapabilities {
  webShare: boolean
  webShareFiles: boolean
  clipboard: boolean
  telegram: boolean
}

export function getShareCapabilities(): ShareCapabilities {
  const nav = (typeof navigator !== 'undefined'
    ? navigator
    : null) as Navigator | null
  return {
    webShare: Boolean(nav && 'share' in nav),
    webShareFiles: Boolean(
      nav &&
        'canShare' in nav &&
        typeof (nav as Navigator & {
          canShare?: (data: ShareData) => boolean
        }).canShare === 'function',
    ),
    clipboard: Boolean(nav?.clipboard?.writeText),
    telegram: isTelegramMiniApp(),
  }
}

/**
 * Open a share intent appropriate for the current platform.
 * Returns true if a native share UI was triggered; false if the
 * caller should fall back (e.g. show its own modal / copy link).
 */
export async function shareNatively(args: {
  url: string
  title?: string
  text?: string
}): Promise<boolean> {
  const caps = getShareCapabilities()
  if (caps.telegram) {
    try {
      const link = `https://t.me/share/url?url=${encodeURIComponent(
        args.url,
      )}${args.text ? `&text=${encodeURIComponent(args.text)}` : ''}`
      const w = window as unknown as {
        Telegram?: {
          WebApp?: { openTelegramLink?: (u: string) => void }
        }
      }
      const open = w.Telegram?.WebApp?.openTelegramLink
      if (open) {
        open(link)
        return true
      }
      window.open(link, '_blank', 'noopener')
      return true
    } catch {
      return false
    }
  }
  if (caps.webShare) {
    try {
      await (navigator as Navigator).share({
        url: args.url,
        title: args.title,
        text: args.text,
      })
      return true
    } catch {
      return false
    }
  }
  return false
}

export async function copyToClipboard(text: string): Promise<boolean> {
  const caps = getShareCapabilities()
  if (caps.clipboard) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      /* fallthrough */
    }
  }
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.setAttribute('readonly', '')
    ta.style.position = 'absolute'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}
