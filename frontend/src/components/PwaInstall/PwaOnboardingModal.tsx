import { useEffect, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { m } from '@/lib/motion'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
import { hapticNotification } from '@/lib/telegram'
import {
  hasDeferredPrompt,
  isIOS,
  isIOSSafari,
  isMobile,
  subscribePromptChange,
  triggerPwaInstall,
} from '@/lib/pwaInstall'
import { InstallGuideModal } from './InstallGuideModal'
import {
  PWA_INSTALL_DISMISS_KEY,
  PWA_ONBOARDING_SEEN_KEY,
} from './pwaOnboardingVisibility'

interface Props {
  onDismiss: () => void
}

export function PwaOnboardingModal({ onDismiss }: Props) {
  const { t } = useTranslation()
  const [bipAvailable, setBipAvailable] = useState(
    hasDeferredPrompt,
  )
  const [showGuide, setShowGuide] = useState(false)
  const ios = isIOS()
  const iosSafari = isIOSSafari()
  const mobile = isMobile()

  useEffect(() => {
    try {
      localStorage.setItem(
        PWA_ONBOARDING_SEEN_KEY,
        String(Date.now()),
      )
      localStorage.setItem(
        PWA_INSTALL_DISMISS_KEY,
        String(Date.now()),
      )
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
    <>
      <AnimatePresence mode="wait" initial={false}>
        {showGuide ? (
          <InstallGuideModal
            key="guide"
            onClose={() => setShowGuide(false)}
            onInstallDone={onDismiss}
          />
        ) : (
          <m.div
            key="onb"
            className="pwa-onb-overlay"
            role="dialog"
            aria-modal="true"
            aria-label={t('pwa.onbTitle')}
            onClick={handleOverlayClick}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            <m.div
              className="pwa-onb-card"
              initial={{ y: 72, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 72, opacity: 0 }}
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

              <ul
                className="pwa-onb-benefits"
                aria-hidden="true"
              >
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

                {mobile && (
                  <button
                    type="button"
                    className="pwa-onb-btn pwa-onb-btn--ghost pwa-onb-btn--guide"
                    onClick={() => setShowGuide(true)}
                  >
                    {t('pwa.guideShowInstructions')}
                  </button>
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
          </m.div>
        )}
      </AnimatePresence>
    </>
  )
}
