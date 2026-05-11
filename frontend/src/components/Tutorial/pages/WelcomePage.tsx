import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { MotionPress } from '@/components/ui/MotionPress'
import { useReducedMotion } from '@/lib/motion'

interface Props {
  onStart: () => void
  disabled?: boolean
}

export function WelcomePage({ onStart, disabled }: Props) {
  const { t } = useTranslation()
  const reduce = useReducedMotion()

  return (
    <div className="tutorial-welcome">
      <motion.div
        className="tutorial-welcome-logo"
        initial={reduce ? { opacity: 1 } : { opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        aria-hidden
      >
        .звук
      </motion.div>
      <motion.h2
        className="tutorial-welcome-title"
        initial={reduce ? { opacity: 1 } : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          delay: reduce ? 0 : 0.12,
          duration: 0.4,
          ease: [0.16, 1, 0.3, 1],
        }}
      >
        {t('redesign.tutorial.welcome.title')}
      </motion.h2>
      <motion.p
        className="tutorial-welcome-body"
        initial={reduce ? { opacity: 1 } : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          delay: reduce ? 0 : 0.2,
          duration: 0.4,
          ease: [0.16, 1, 0.3, 1],
        }}
      >
        {t('redesign.tutorial.welcome.body')}
      </motion.p>
      <motion.div
        className="tutorial-welcome-cta"
        initial={reduce ? { opacity: 1 } : { opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{
          delay: reduce ? 0 : 0.3,
          duration: 0.4,
          ease: [0.16, 1, 0.3, 1],
        }}
      >
        <MotionPress
          type="button"
          variant="primary"
          haptic="medium"
          className="onboarding-next tutorial-welcome-button"
          onClick={onStart}
          disabled={disabled}
        >
          {t('redesign.tutorial.welcome.cta')}
        </MotionPress>
      </motion.div>
    </div>
  )
}
