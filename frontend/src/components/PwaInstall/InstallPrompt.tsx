import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { useToast } from '@/components/ui/Toast'
import {
  hapticNotification,
  isTelegram,
} from '@/lib/telegram'

const STORAGE_KEY = 'pwa-install-dismissed-at'
const VISIT_KEY = 'pwa-visit-count'
const DELAY_MS = 30_000
const FALLBACK_NO_BIP_MS = 55_000
const MIN_VISITS = 2

type PanelMode =
  | 'bip'
  | 'ios_safari'
  | 'ios_other'
  | 'menu_hint'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{
    outcome: 'accepted' | 'dismissed'
  }>
}

function isStandalone(): boolean {
  try {
    return (
      window.matchMedia(
        '(display-mode: standalone)',
      ).matches ||
      (window.navigator as Navigator & {
        standalone?: boolean
      }).standalone === true
    )
  } catch {
    return false
  }
}

function isIOS(): boolean {
  try {
    const ua = navigator.userAgent || ''
    if (/iPad|iPhone|iPod/.test(ua)) {
      return true
    }
    if (
      /Mac/.test(navigator.platform)
      && ((navigator as Navigator & { maxTouchPoints?: number })
        .maxTouchPoints ?? 0) > 1
    ) {
      return true
    }
    return false
  } catch {
    return false
  }
}

function isIOSSafariForCopy(): boolean {
  try {
    const ua = navigator.userAgent || ''
    if (!isIOS()) return false
    return (
      /Safari/.test(ua)
      && !/CriOS|FxiOS|EdgiOS|OPiOS|OPT\//.test(ua)
    )
  } catch {
    return false
  }
}

function recentlyDismissed(): boolean {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (!v) return false
    const dismissedAt = Number(v)
    const days =
      (Date.now() - dismissedAt) / (1000 * 60 * 60 * 24)
    return days < 14
  } catch {
    return false
  }
}

function bumpVisits(): number {
  try {
    const n = Number(
      localStorage.getItem(VISIT_KEY) || '0',
    )
    const next = n + 1
    localStorage.setItem(VISIT_KEY, String(next))
    return next
  } catch {
    return MIN_VISITS
  }
}

export function InstallPrompt() {
  const { t } = useTranslation()
  const [visible, setVisible] = useState(false)
  const [panelMode, setPanelMode] = useState<PanelMode | null>(
    null,
  )
  const promptRef =
    useRef<BeforeInstallPromptEvent | null>(null)
  const bipEventReceived = useRef(false)
  const toast = useToast()

  useEffect(() => {
    if (isTelegram()) return
    if (isStandalone()) return
    if (recentlyDismissed()) return
    const visits = bumpVisits()
    if (visits < MIN_VISITS) return

    const onBefore = (e: Event) => {
      e.preventDefault()
      if (isIOS()) {
        return
      }
      bipEventReceived.current = true
      promptRef.current =
        e as BeforeInstallPromptEvent
      setPanelMode('bip')
      window.setTimeout(
        () => setVisible(true),
        DELAY_MS,
      )
    }
    const onInstalled = () => {
      setVisible(false)
      setPanelMode(null)
      try {
        localStorage.setItem(
          STORAGE_KEY,
          String(Date.now()),
        )
      } catch {
        /* ignore */
      }
      toast.success(t('pwa.installed'))
      hapticNotification('success')
    }

    window.addEventListener(
      'beforeinstallprompt',
      onBefore as EventListener,
    )
    window.addEventListener(
      'appinstalled',
      onInstalled,
    )

    let tIos: ReturnType<typeof setTimeout> | undefined
    if (isIOS()) {
      tIos = setTimeout(() => {
        setPanelMode(
          isIOSSafariForCopy()
            ? 'ios_safari'
            : 'ios_other',
        )
        setVisible(true)
      }, DELAY_MS)
    } else {
      tIos = setTimeout(() => {
        if (bipEventReceived.current) {
          return
        }
        setPanelMode('menu_hint')
        setVisible(true)
      }, FALLBACK_NO_BIP_MS)
    }

    return () => {
      if (tIos !== undefined) {
        clearTimeout(tIos)
      }
      window.removeEventListener(
        'beforeinstallprompt',
        onBefore as EventListener,
      )
      window.removeEventListener(
        'appinstalled',
        onInstalled,
      )
    }
  }, [toast, t])

  if (!visible || panelMode === null) {
    return null
  }

  const dismiss = (persist = true) => {
    setVisible(false)
    setPanelMode(null)
    if (persist) {
      try {
        localStorage.setItem(
          STORAGE_KEY,
          String(Date.now()),
        )
      } catch {
        /* ignore */
      }
    }
  }

  const install = async () => {
    const evt = promptRef.current
    if (!evt) {
      dismiss()
      return
    }
    try {
      await evt.prompt()
      const choice = await evt.userChoice
      if (choice.outcome === 'accepted') {
        hapticNotification('success')
      }
      dismiss(choice.outcome === 'dismissed')
    } catch {
      dismiss()
    }
  }

  const hint = () => {
    switch (panelMode) {
      case 'ios_safari':
        return t('pwa.safari')
      case 'ios_other':
        return t('pwa.ios')
      case 'menu_hint':
        return t('pwa.other')
      case 'bip':
      default:
        return t('pwa.valueProp')
    }
  }

  const usePrimaryForInstall =
    panelMode === 'bip' && promptRef.current !== null

  return (
    <div
      className="install-prompt"
      role="dialog"
      aria-label={t('pwa.installLabel')}
    >
      <div className="install-prompt__icon">
        <Icon name="install" size={22} />
      </div>
      <div className="install-prompt__body">
        <div className="install-prompt__title">
          {t('pwa.installLabel')}
        </div>
        <div className="install-prompt__hint">
          {hint()}
        </div>
      </div>
      <div className="install-prompt__actions">
        {usePrimaryForInstall ? (
          <button
            className="install-prompt__btn primary"
            onClick={install}
            type="button"
          >
            {t('pwa.installCta')}
          </button>
        ) : (
          <button
            className="install-prompt__btn primary"
            onClick={() => dismiss(true)}
            type="button"
          >
            {t('pwa.ok')}
          </button>
        )}
        <button
          className="install-prompt__btn"
          onClick={() => dismiss(true)}
          aria-label={t('pwa.closeAria')}
          type="button"
        >
          <Icon name="x" size={16} />
        </button>
      </div>
    </div>
  )
}

export function canInstallPwa(): boolean {
  try {
    return (
      !isTelegram() &&
      !isStandalone() &&
      'serviceWorker' in navigator
    )
  } catch {
    return false
  }
}
