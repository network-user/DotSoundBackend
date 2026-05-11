import { useCallback, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  AnimatePresence,
  motion,
  type PanInfo,
} from 'framer-motion'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  SPRING_GENTLE,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { WelcomePage } from './pages/WelcomePage'
import { RadioPage } from './pages/RadioPage'
import { ImportPage } from './pages/ImportPage'
import { CardsPage } from './pages/CardsPage'
import { MixPage } from './pages/MixPage'
import { ReadyPage } from './pages/ReadyPage'

interface Props {
  onComplete: () => void
}

const PAGE_KEYS = [
  'welcome',
  'radio',
  'import',
  'cards',
  'mix',
  'ready',
] as const

const TR = (key: string) => `redesign.tutorial.${key}`

export function WelcomeTutorial({ onComplete }: Props) {
  const { t } = useTranslation()
  const reduceMotion = useReducedMotion()
  const [index, setIndex] = useState(0)
  const [finishing, setFinishing] = useState(false)

  const pageKey = PAGE_KEYS[index]
  const isWelcome = pageKey === 'welcome'
  const isLast = index === PAGE_KEYS.length - 1
  const Page = pageKey

  const finish = useCallback(async () => {
    if (finishing) return
    setFinishing(true)
    try {
      await api.acknowledgeTutorial()
    } catch {
      /* best-effort */
    }
    onComplete()
  }, [finishing, onComplete])

  const next = useCallback(() => {
    if (isLast) {
      void finish()
      return
    }
    setIndex((i) => Math.min(i + 1, PAGE_KEYS.length - 1))
  }, [isLast, finish])

  const back = useCallback(() => {
    setIndex((i) => Math.max(i - 1, 0))
  }, [])

  const handlePan = useCallback(
    (_: unknown, info: PanInfo) => {
      const dx = info.offset.x
      const threshold = 80
      if (dx < -threshold) {
        next()
      } else if (dx > threshold) {
        back()
      }
    },
    [next, back],
  )

  const variants = useMemo(() => {
    if (reduceMotion) {
      return {
        initial: { opacity: 0 },
        animate: { opacity: 1, transition: TWEEN_FAST },
        exit: { opacity: 0, transition: TWEEN_FAST },
      }
    }
    return {
      initial: { opacity: 0, x: 32 },
      animate: { opacity: 1, x: 0, transition: SPRING_GENTLE },
      exit: { opacity: 0, x: -24, transition: TWEEN_FAST },
    }
  }, [reduceMotion])

  const renderPage = () => {
    switch (Page) {
      case 'welcome':
        return (
          <WelcomePage onStart={next} disabled={finishing} />
        )
      case 'radio':
        return <RadioPage />
      case 'import':
        return <ImportPage />
      case 'cards':
        return <CardsPage />
      case 'mix':
        return <MixPage />
      case 'ready':
        return <ReadyPage />
      default:
        return null
    }
  }

  return (
    <div className="welcome-tutorial">
      <div
        className={
          'welcome-tutorial-stage' +
          (isWelcome ? ' is-welcome' : '')
        }
      >
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={pageKey}
            className={
              'welcome-tutorial-page' +
              (isWelcome ? ' is-welcome' : '')
            }
            initial={variants.initial}
            animate={variants.animate}
            exit={variants.exit}
            drag="x"
            dragConstraints={{ left: 0, right: 0 }}
            dragElastic={0.25}
            onPanEnd={handlePan}
          >
            {renderPage()}
            {!isWelcome && (
              <>
                <h2 className="welcome-tutorial-title">
                  {t(TR(`${pageKey}.title`))}
                </h2>
                <p className="welcome-tutorial-body">
                  {t(TR(`${pageKey}.body`))}
                </p>
              </>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="welcome-tutorial-footer">
        <div className="welcome-tutorial-dots" aria-hidden>
          {PAGE_KEYS.map((k, i) => (
            <span
              key={k}
              className={
                'welcome-tutorial-dot' +
                (i === index ? ' is-active' : '')
              }
            />
          ))}
        </div>
        <div className="welcome-tutorial-controls">
          {index > 0 ? (
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="onboarding-skip"
              onClick={back}
              disabled={finishing}
              ariaLabel={t(TR('back'))}
            >
              <Icon name="chevron-left" size={18} />
              {t(TR('back'))}
            </MotionPress>
          ) : (
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="onboarding-skip"
              onClick={() => void finish()}
              disabled={finishing}
            >
              {t(TR('skip'))}
            </MotionPress>
          )}
          {!isWelcome && (
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="onboarding-next"
              onClick={next}
              disabled={finishing}
            >
              {isLast ? t(TR('start')) : t(TR('next'))}
            </MotionPress>
          )}
        </div>
      </div>
    </div>
  )
}
