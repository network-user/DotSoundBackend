import { useEffect, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { m, SPRING_GENTLE } from '@/lib/motion'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
import { haptic, hapticNotification } from '@/lib/telegram'
import {
  type Platform,
  getPlatform,
  hasDeferredPrompt,
  subscribePromptChange,
  triggerPwaInstall,
} from '@/lib/pwaInstall'

// ── Step definitions ─────────────────────────────────────

interface StepDef {
  titleKey: string
  descKey: string
}

const STEPS: Record<Platform, StepDef[]> = {
  'ios-safari': [
    {
      titleKey: 'pwa.iosSafariStep1Title',
      descKey: 'pwa.iosSafariStep1Desc',
    },
    {
      titleKey: 'pwa.iosSafariStep2Title',
      descKey: 'pwa.iosSafariStep2Desc',
    },
    {
      titleKey: 'pwa.iosSafariStep3Title',
      descKey: 'pwa.iosSafariStep3Desc',
    },
  ],
  'ios-other': [
    {
      titleKey: 'pwa.iosOtherStep1Title',
      descKey: 'pwa.iosOtherStep1Desc',
    },
    {
      titleKey: 'pwa.iosOtherStep2Title',
      descKey: 'pwa.iosOtherStep2Desc',
    },
  ],
  'android-bip': [
    {
      titleKey: 'pwa.androidBipStep1Title',
      descKey: 'pwa.androidBipStep1Desc',
    },
  ],
  'android-other': [
    {
      titleKey: 'pwa.androidOtherStep1Title',
      descKey: 'pwa.androidOtherStep1Desc',
    },
    {
      titleKey: 'pwa.androidOtherStep2Title',
      descKey: 'pwa.androidOtherStep2Desc',
    },
  ],
}

// ── Step visual mockups ──────────────────────────────────

function StepVisual({
  platform,
  step,
}: {
  platform: Platform
  step: number
}) {
  if (platform === 'ios-safari') {
    if (step === 0) {
      return (
        <div className="ig-visual">
          <div className="ig-mock-phone">
            <div className="ig-mock-content">
              <div className="ig-mock-address-pill">
                .звук
              </div>
            </div>
            <div className="ig-mock-ios-toolbar">
              <span className="ig-mock-nav-btn">‹</span>
              <span className="ig-mock-nav-btn ig-mock-nav-btn--dim">›</span>
              <span className="ig-mock-spacer" />
              <span className="ig-mock-share-btn ig-mock-highlight-ring">
                <Icon name="share" size={16} />
              </span>
              <span className="ig-mock-spacer" />
              <span className="ig-mock-nav-btn">⊡</span>
            </div>
          </div>
        </div>
      )
    }
    if (step === 1) {
      return (
        <div className="ig-visual">
          <div className="ig-mock-sheet">
            <div className="ig-mock-sheet-grip" />
            <div className="ig-mock-sheet-item">
              <Icon name="link" size={13} />
              <span>Копировать ссылку</span>
            </div>
            <div className="ig-mock-sheet-item ig-mock-item-highlight">
              <Icon name="home" size={13} />
              <span>На экран «Домой»</span>
              <span className="ig-mock-tap-ring" />
            </div>
            <div className="ig-mock-sheet-item">
              <Icon name="download" size={13} />
              <span>Закладки</span>
            </div>
          </div>
        </div>
      )
    }
    if (step === 2) {
      return (
        <div className="ig-visual">
          <div className="ig-mock-dialog">
            <div className="ig-mock-dialog-title">
              На экран «Домой»
            </div>
            <div className="ig-mock-dialog-app">
              <div className="ig-mock-app-icon">
                <Icon name="music" size={14} />
              </div>
              <span>.звук</span>
            </div>
            <div className="ig-mock-dialog-btns">
              <span className="ig-mock-dialog-btn">
                Отменить
              </span>
              <span className="ig-mock-dialog-btn ig-mock-item-highlight">
                Добавить
              </span>
            </div>
          </div>
        </div>
      )
    }
  }

  if (platform === 'ios-other') {
    if (step === 0) {
      return (
        <div className="ig-visual">
          <div className="ig-mock-phone">
            <div className="ig-mock-content">
              <div className="ig-mock-address-pill">
                .звук
              </div>
            </div>
            <div className="ig-mock-ios-toolbar">
              <span className="ig-mock-nav-btn">‹</span>
              <span className="ig-mock-nav-btn ig-mock-nav-btn--dim">›</span>
              <span className="ig-mock-spacer" />
              <span className="ig-mock-share-btn ig-mock-highlight-ring">
                <Icon name="share" size={16} />
              </span>
              <span className="ig-mock-dots-btn ig-mock-highlight-ring">
                •••
              </span>
            </div>
          </div>
        </div>
      )
    }
    if (step === 1) {
      return (
        <div className="ig-visual">
          <div className="ig-mock-sheet">
            <div className="ig-mock-sheet-grip" />
            <div className="ig-mock-sheet-item ig-mock-item-highlight">
              <Icon name="home" size={13} />
              <span>На экран «Домой»</span>
              <span className="ig-mock-tap-ring" />
            </div>
            <div className="ig-mock-sheet-item">
              <Icon name="share" size={13} />
              <span>Поделиться</span>
            </div>
            <div className="ig-mock-sheet-item">
              <Icon name="link" size={13} />
              <span>Скопировать</span>
            </div>
          </div>
        </div>
      )
    }
  }

  if (platform === 'android-bip') {
    return (
      <div className="ig-visual">
        <div className="ig-mock-bip">
          <div className="ig-mock-bip-icon">
            <Icon name="install" size={30} />
          </div>
          <div className="ig-mock-bip-pulse" />
        </div>
      </div>
    )
  }

  if (platform === 'android-other') {
    if (step === 0) {
      return (
        <div className="ig-visual">
          <div className="ig-mock-android-chrome">
            <div className="ig-mock-android-bar">
              <span className="ig-mock-nav-btn">←</span>
              <span className="ig-mock-address-pill ig-mock-address-pill--android">
                .звук
              </span>
              <span className="ig-mock-three-dots ig-mock-highlight-ring">
                ⋮
              </span>
            </div>
          </div>
        </div>
      )
    }
    if (step === 1) {
      return (
        <div className="ig-visual ig-visual--menu">
          <div className="ig-mock-dropdown">
            <div className="ig-mock-sheet-item">
              Новая вкладка
            </div>
            <div className="ig-mock-sheet-item ig-mock-item-highlight">
              <Icon name="install" size={13} />
              <span>Установить приложение</span>
              <span className="ig-mock-tap-ring" />
            </div>
            <div className="ig-mock-sheet-item">
              Закладки
            </div>
            <div className="ig-mock-sheet-item">
              История
            </div>
          </div>
        </div>
      )
    }
  }

  return <div className="ig-visual" />
}

// ── Main component ───────────────────────────────────────

interface Props {
  onClose: () => void
  onInstallDone: () => void
}

const slideVariants = {
  enter: (dir: number) => ({
    x: dir > 0 ? 56 : -56,
    opacity: 0,
  }),
  center: { x: 0, opacity: 1 },
  exit: (dir: number) => ({
    x: dir > 0 ? -56 : 56,
    opacity: 0,
  }),
}

const slideTrans = {
  type: 'spring' as const,
  stiffness: 400,
  damping: 36,
}

export function InstallGuideModal({
  onClose,
  onInstallDone,
}: Props) {
  const { t } = useTranslation()
  const [platform] = useState<Platform>(getPlatform)
  const [step, setStep] = useState(0)
  const [dir, setDir] = useState(1)
  const [bipAvailable, setBipAvailable] = useState(
    hasDeferredPrompt,
  )

  useEffect(() => {
    return subscribePromptChange(() => {
      setBipAvailable(hasDeferredPrompt())
    })
  }, [])

  const steps = STEPS[platform]
  const total = steps.length
  const isLast = step === total - 1
  const isFirst = step === 0

  const goNext = () => {
    setDir(1)
    setStep((s) => Math.min(s + 1, total - 1))
    haptic('light')
  }

  const goPrev = () => {
    setDir(-1)
    setStep((s) => Math.max(s - 1, 0))
    haptic('light')
  }

  const handleInstall = async () => {
    const result = await triggerPwaInstall()
    if (result === 'accepted') {
      hapticNotification('success')
      showIsland({
        kind: 'toast',
        title: t('pwa.installed'),
        durationMs: 2400,
      })
      onInstallDone()
    }
    onClose()
  }

  const showInstallBtn =
    platform === 'android-bip' && bipAvailable

  return (
    <div
      className="ig-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={t('pwa.guideTitle')}
    >
      <m.div
        className="ig-card"
        initial={{ y: 72, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 72, opacity: 0 }}
        transition={SPRING_GENTLE}
      >
        {/* Header */}
        <div className="ig-header">
          <button
            type="button"
            className="ig-icon-btn"
            aria-label={t('pwa.guidePrev')}
            onClick={onClose}
          >
            <span className="ig-chevron-left" aria-hidden="true">
              <Icon name="chevron" size={18} />
            </span>
          </button>
          <span className="ig-header-title">
            {t('pwa.guideTitle')}
          </span>
          <button
            type="button"
            className="ig-icon-btn"
            aria-label={t('pwa.closeAria')}
            onClick={onInstallDone}
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        {/* Step dots */}
        <div
          className="ig-dots"
          role="progressbar"
          aria-valuenow={step + 1}
          aria-valuemax={total}
          aria-label={t('pwa.guideStepOf', {
            current: step + 1,
            total,
          })}
        >
          {steps.map((_, i) => (
            <span
              key={i}
              className={
                'ig-dot' +
                (i === step ? ' ig-dot--active' : '') +
                (i < step ? ' ig-dot--done' : '')
              }
            />
          ))}
        </div>

        {/* Animated step content */}
        <div className="ig-viewport">
          <AnimatePresence
            custom={dir}
            mode="wait"
            initial={false}
          >
            <m.div
              key={step}
              custom={dir}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={slideTrans}
              className="ig-step"
            >
              <StepVisual platform={platform} step={step} />

              <div className="ig-step-text">
                <span className="ig-step-counter">
                  {t('pwa.guideStepOf', {
                    current: step + 1,
                    total,
                  })}
                </span>
                <h3 className="ig-step-title">
                  {t(steps[step].titleKey)}
                </h3>
                <p className="ig-step-desc">
                  {t(steps[step].descKey)}
                </p>
              </div>
            </m.div>
          </AnimatePresence>
        </div>

        {/* Navigation */}
        <div className="ig-nav">
          <MotionPress
            variant="ghost"
            className="ig-nav-btn ig-nav-btn--back"
            haptic="light"
            disabled={isFirst}
            onClick={goPrev}
            aria-label={t('pwa.guidePrev')}
          >
            <span
              className="ig-chevron-left"
              aria-hidden="true"
            >
              <Icon name="chevron" size={15} />
            </span>
            {t('pwa.guidePrev')}
          </MotionPress>

          {showInstallBtn ? (
            <MotionPress
              variant="primary"
              className="ig-nav-btn ig-nav-btn--primary"
              haptic="medium"
              onClick={() => void handleInstall()}
            >
              {t('pwa.onbInstallCta')}
            </MotionPress>
          ) : isLast ? (
            <MotionPress
              variant="primary"
              className="ig-nav-btn ig-nav-btn--primary"
              haptic="light"
              onClick={onClose}
            >
              {t('pwa.ok')}
            </MotionPress>
          ) : (
            <MotionPress
              variant="primary"
              className="ig-nav-btn ig-nav-btn--primary"
              haptic="light"
              onClick={goNext}
            >
              {t('pwa.guideNext')}
              <Icon name="chevron" size={15} />
            </MotionPress>
          )}
        </div>
      </m.div>
    </div>
  )
}
