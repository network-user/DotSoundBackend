import { useCallback, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AnimatePresence, motion } from 'framer-motion'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  SPRING_GENTLE,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { RadioPage } from './pages/RadioPage'
import { ImportPage } from './pages/ImportPage'
import { CardsPage } from './pages/CardsPage'
import { SwipesPage } from './pages/SwipesPage'
import { ReadyPage } from './pages/ReadyPage'

interface Props {
  onComplete: () => void
}

const PAGE_KEYS = ['radio', 'import', 'cards', 'swipes', 'ready'] as const
type PageKey = (typeof PAGE_KEYS)[number]

const PAGE_COMPONENTS: Record<PageKey, () => JSX.Element> = {
  radio: RadioPage,
  import: ImportPage,
  cards: CardsPage,
  swipes: SwipesPage,
  ready: ReadyPage,
}

export function WelcomeTutorial({ onComplete }: Props) {
  const { t } = useTranslation()
  const reduceMotion = useReducedMotion()
  const [index, setIndex] = useState(0)
  const [finishing, setFinishing] = useState(false)

  const pageKey = PAGE_KEYS[index]
  const isLast = index === PAGE_KEYS.length - 1
  const Page = PAGE_COMPONENTS[pageKey]

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

  return (
    <div className="welcome-tutorial">
      <div className="welcome-tutorial-stage">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={pageKey}
            className="welcome-tutorial-page"
            initial={variants.initial}
            animate={variants.animate}
            exit={variants.exit}
          >
            <Page />
            <h2 className="welcome-tutorial-title">
              {t(`tutorial.${pageKey}.title`)}
            </h2>
            <p className="welcome-tutorial-body">
              {t(`tutorial.${pageKey}.body`)}
            </p>
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
              ariaLabel={t('tutorial.back')}
            >
              <Icon name="chevron-left" size={18} />
              {t('tutorial.back')}
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
              {t('tutorial.skip')}
            </MotionPress>
          )}
          <MotionPress
            type="button"
            variant="primary"
            haptic="medium"
            className="onboarding-next"
            onClick={next}
            disabled={finishing}
          >
            {isLast ? t('tutorial.start') : t('tutorial.next')}
          </MotionPress>
        </div>
      </div>
    </div>
  )
}
