import { useEffect, useRef, useState } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { useToast } from '@/components/ui/Toast'
import {
  hapticNotification,
  isTelegram,
} from '@/lib/telegram'

const STORAGE_KEY = 'pwa-install-dismissed-at'
const VISIT_KEY = 'pwa-visit-count'
const DELAY_MS = 30_000
const MIN_VISITS = 2

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

function isIOSSafari(): boolean {
  try {
    const ua = navigator.userAgent || ''
    const iOS = /iPad|iPhone|iPod/.test(ua)
    const safari =
      /Safari/.test(ua) && !/CriOS|FxiOS/.test(ua)
    return iOS && safari
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
  const [visible, setVisible] = useState(false)
  const [iosFlow, setIosFlow] = useState(false)
  const promptRef =
    useRef<BeforeInstallPromptEvent | null>(null)
  const toast = useToast()

  useEffect(() => {
    if (isTelegram()) return
    if (isStandalone()) return
    if (recentlyDismissed()) return
    const visits = bumpVisits()
    if (visits < MIN_VISITS) return

    const onBefore = (e: Event) => {
      e.preventDefault()
      promptRef.current =
        e as BeforeInstallPromptEvent
      setIosFlow(false)
      window.setTimeout(
        () => setVisible(true),
        DELAY_MS,
      )
    }
    const onInstalled = () => {
      setVisible(false)
      try {
        localStorage.setItem(
          STORAGE_KEY,
          String(Date.now()),
        )
      } catch {
        /* ignore */
      }
      toast.success('Приложение установлено')
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

    if (isIOSSafari()) {
      window.setTimeout(() => {
        setIosFlow(true)
        setVisible(true)
      }, DELAY_MS)
    }

    return () => {
      window.removeEventListener(
        'beforeinstallprompt',
        onBefore as EventListener,
      )
      window.removeEventListener(
        'appinstalled',
        onInstalled,
      )
    }
  }, [toast])

  if (!visible) return null

  const dismiss = (persist = true) => {
    setVisible(false)
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

  return (
    <div
      className="install-prompt"
      role="dialog"
      aria-label="Установить .sound"
    >
      <div className="install-prompt__icon">
        <Icon name="install" size={22} />
      </div>
      <div className="install-prompt__body">
        <div className="install-prompt__title">
          Установить .sound
        </div>
        {iosFlow ? (
          <div className="install-prompt__hint">
            Откройте «Поделиться» в Safari и
            выберите «На экран Домой».
          </div>
        ) : (
          <div className="install-prompt__hint">
            Получайте плеер в одно касание с
            рабочего стола.
          </div>
        )}
      </div>
      <div className="install-prompt__actions">
        {iosFlow ? (
          <button
            className="install-prompt__btn primary"
            onClick={() => dismiss(true)}
          >
            Понятно
          </button>
        ) : (
          <button
            className="install-prompt__btn primary"
            onClick={install}
          >
            Установить
          </button>
        )}
        <button
          className="install-prompt__btn"
          onClick={() => dismiss(true)}
          aria-label="Закрыть"
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
