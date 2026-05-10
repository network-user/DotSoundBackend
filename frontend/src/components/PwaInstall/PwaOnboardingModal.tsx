import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { m } from '@/lib/motion'
import { showIsland } from '@/lib/island'
import { hapticNotification, isTelegram } from '@/lib/telegram'
import {
  hasDeferredPrompt,
  subscribePromptChange,
  triggerPwaInstall,
} from '@/lib/pwaInstall'

const SEEN_KEY = 'pwa-onb-seen'
const DISMISS_KEY = 'pwa-install-dismissed-at'

function isStandalone(): boolean {
  try {
    return (
      window.matchMedia('(display-mode: standalone)').matches ||
      (
        window.navigator as Navigator & { standalone?: boolean }
      ).standalone === true
    )
  } catch {
    return false
  }
}

function isIOS(): boolean {
  try {
    const ua = navigator.userAgent || ''
    if (/iPad|iPhone|iPod/.test(ua)) return true
    if (
      /Mac/.test(navigator.platform) &&
      ((navigator as Navigator & { maxTouchPoints?: number })
        .maxTouchPoints ?? 0) > 1
    )
      return true
    return false
  } catch {
    return false
  }
}

function isIOSSafari(): boolean {
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

export function shouldShowPwaOnboardingModal(): boolean {
  if (isTelegram()) return false
  if (isStandalone()) return false
  try {
    return !localStorage.getItem(SEEN_KEY)
  } catch {
    return false
  }
}

interface Props {
  onDismiss: () => void
}

export function PwaOnboardingModal({ onDismiss }: Props) {
  const { t } = useTranslation()
  const [bipAvailable, setBipAvailable] = useState(
    hasDeferredPrompt,
  )
  const ios = isIOS()
  const iosSafari = isIOSSafari()

  useEffect(() => {
    try {
      localStorage.setItem(SEEN_KEY, String(Date.now()))
      localStorage.setItem(DISMISS_KEY, String(Date.now()))
    } catch {
      /* ignore */
    }
    return subscribePromptChange(() => {
      setBipAvailable(hasDeferredPrompt())
    })
  }, [])

  const handleInstall = async () => {
    const result = await triggerPwaInstall()
    if (result === 'accepted') {
      showIsland({
        kind: 'toast',
        title: t('pwa.installed'),
        durationMs: 2400,
      })
      hapticNotification('success')
    }
    onDismiss()
  }

  const handleOverlayClick = (
    e: React.MouseEvent<HTMLDivElement>,
  ) => {
    if (e.target === e.currentTarget) onDismiss()
  }

  const showInstallBtn = bipAvailable && !ios

  return (
    <div
      className="pwa-onb-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={t('pwa.onbTitle')}
      onClick={handleOverlayClick}
    >
      <m.div
        className="pwa-onb-card"
        initial={{ y: 72, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{
          type: 'spring',
          stiffness: 340,
          damping: 32,
        }}
      >
        <div
          className="pwa-onb-icon-wrap"
          aria-hidden="true"
        >
          <Icon name="smartphone" size={30} />
        </div>

        <h2 className="pwa-onb-title">
          {t('pwa.onbTitle')}
        </h2>
        <p className="pwa-onb-subtitle">
          {t('pwa.onbSubtitle')}
        </p>

        <ul className="pwa-onb-benefits" aria-hidden="true">
          <li>{t('pwa.onbBenefit1')}</li>
          <li>{t('pwa.onbBenefit2')}</li>
          <li>{t('pwa.onbBenefit3')}</li>
        </ul>

        {ios && (
          <div className="pwa-onb-ios-steps">
            <div className="pwa-onb-ios-step">
              <span className="pwa-onb-ios-num">1</span>
              <span className="pwa-onb-ios-text">
                {iosSafari
                  ? t('pwa.onbIosSafariStep1')
                  : t('pwa.onbIosOtherStep1')}
                {' '}
                <span
                  className="pwa-onb-ios-share-icon"
                  aria-hidden="true"
                >
                  <Icon name="share" size={13} />
                </span>
              </span>
            </div>
            <div className="pwa-onb-ios-step">
              <span className="pwa-onb-ios-num">2</span>
              <span className="pwa-onb-ios-text">
                {t('pwa.onbIosStep2')}
              </span>
            </div>
          </div>
        )}

        {!ios && !showInstallBtn && (
          <p className="pwa-onb-hint">
            {t('pwa.onbMenuHint')}
          </p>
        )}

        <div className="pwa-onb-actions">
          {showInstallBtn ? (
            <MotionPress
              variant="primary"
              className="pwa-onb-btn pwa-onb-btn--primary"
              haptic="medium"
              onClick={() => void handleInstall()}
            >
              {t('pwa.onbInstallCta')}
            </MotionPress>
          ) : (
            <MotionPress
              variant="primary"
              className="pwa-onb-btn pwa-onb-btn--primary"
              haptic="light"
              onClick={onDismiss}
            >
              {t('pwa.ok')}
            </MotionPress>
          )}
          <button
            type="button"
            className="pwa-onb-btn pwa-onb-btn--ghost"
            onClick={onDismiss}
          >
            {t('pwa.onbLater')}
          </button>
        </div>
      </m.div>
    </div>
  )
}
