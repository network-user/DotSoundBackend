import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { showIsland } from '@/lib/island'
import { MotionPress } from '@/components/ui/MotionPress'
import { m, VARIANTS_FADE_UP } from '@/lib/motion'
import { hapticNotification, isTelegram } from '@/lib/telegram'
import {
  hasDeferredPrompt,
  isIOS,
  isIOSSafari,
  isStandalone,
  subscribePromptChange,
  triggerPwaInstall,
} from '@/lib/pwaInstall'

const STORAGE_KEY = 'pwa-install-dismissed-at'
const VISIT_KEY = 'pwa-visit-count'
const ONB_SEEN_KEY = 'pwa-onb-seen'
const DELAY_MS = 30_000
const FALLBACK_NO_BIP_MS = 55_000
const MIN_VISITS = 2

type PanelMode =
  | 'bip'
  | 'ios_safari'
  | 'ios_other'
  | 'menu_hint'

function recentlyDismissed(): boolean {
  try {
    const v =
      localStorage.getItem(STORAGE_KEY) ||
      localStorage.getItem(ONB_SEEN_KEY)
    if (!v) return false
    const days =
      (Date.now() - Number(v)) /
      (1000 * 60 * 60 * 24)
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
  const [panelMode, setPanelMode] =
    useState<PanelMode | null>(null)
  const [bipAvailable, setBipAvailable] = useState(
    hasDeferredPrompt,
  )

  useEffect(() => {
    if (isTelegram()) return
    if (isStandalone()) return
    if (recentlyDismissed()) return
    const visits = bumpVisits()
    if (visits < MIN_VISITS) return

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
      showIsland({
        kind: 'toast',
        title: t('pwa.installed'),
        durationMs: 2400,
      })
      hapticNotification('success')
    }
    window.addEventListener('appinstalled', onInstalled)

    let tDelay: number | undefined
    let tFallback: number | undefined

    const unsubBip = subscribePromptChange(() => {
      const available = hasDeferredPrompt()
      setBipAvailable(available)
      if (available && !isIOS()) {
        clearTimeout(tFallback)
        setPanelMode('bip')
        tDelay = window.setTimeout(
          () => setVisible(true),
          DELAY_MS,
        )
      }
    })

    if (hasDeferredPrompt() && !isIOS()) {
      setPanelMode('bip')
      tDelay = window.setTimeout(
        () => setVisible(true),
        DELAY_MS,
      )
    } else if (isIOS()) {
      tDelay = window.setTimeout(() => {
        setPanelMode(
          isIOSSafari() ? 'ios_safari' : 'ios_other',
        )
        setVisible(true)
      }, DELAY_MS)
    } else {
      tFallback = window.setTimeout(() => {
        if (hasDeferredPrompt()) return
        setPanelMode('menu_hint')
        setVisible(true)
      }, FALLBACK_NO_BIP_MS)
    }

    return () => {
      clearTimeout(tDelay)
      clearTimeout(tFallback)
      unsubBip()
      window.removeEventListener(
        'appinstalled',
        onInstalled,
      )
    }
  }, [t])

  if (!visible || panelMode === null) return null

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
    const result = await triggerPwaInstall()
    if (result === null) { dismiss(); return }
    if (result === 'accepted') hapticNotification('success')
    dismiss(result === 'dismissed')
  }

  const hint = () => {
    switch (panelMode) {
      case 'ios_safari': return t('pwa.safari')
      case 'ios_other':  return t('pwa.ios')
      case 'menu_hint':  return t('pwa.other')
      default:           return t('pwa.valueProp')
    }
  }

  const usePrimaryForInstall =
    panelMode === 'bip' && bipAvailable

  return (
    <m.div
      className="install-prompt rb-install glass--medium"
      role="dialog"
      aria-label={t('pwa.installLabel')}
      initial="hidden"
      animate="visible"
      variants={VARIANTS_FADE_UP}
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
          <MotionPress
            variant="primary"
            className="install-prompt__btn primary"
            haptic="medium"
            onClick={() => void install()}
          >
            {t('pwa.installCta')}
          </MotionPress>
        ) : (
          <MotionPress
            variant="primary"
            className="install-prompt__btn primary"
            haptic="light"
            onClick={() => dismiss(true)}
          >
            {t('pwa.ok')}
          </MotionPress>
        )}
        <MotionPress
          variant="ghost"
          className="install-prompt__btn"
          ariaLabel={t('pwa.closeAria')}
          haptic="light"
          onClick={() => dismiss(true)}
        >
          <Icon name="x" size={16} />
        </MotionPress>
      </div>
    </m.div>
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
