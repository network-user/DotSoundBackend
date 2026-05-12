import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { Icon } from '@/components/Icon/Icon'
import { useReducedMotion } from '@/lib/motion'
import { markTelegramBrowserHintTutorialSeen } from '@/lib/telegramBrowserHint'

export function BrowserPage() {
  const reduce = useReducedMotion()

  useEffect(() => {
    markTelegramBrowserHintTutorialSeen()
  }, [])

  return (
    <div className="tutorial-illustration tutorial-illustration-browser">
      <div className="tutorial-browser-scene" aria-hidden>
        <motion.div
          className="tutorial-browser-orbit"
          animate={
            reduce
              ? { opacity: 0.35 }
              : { opacity: [0.22, 0.45, 0.22], scale: [1, 1.04, 1] }
          }
          transition={{
            duration: 2.8,
            repeat: reduce ? 0 : Infinity,
            ease: 'easeInOut',
          }}
        />
        <div className="tutorial-browser-window">
          <div className="tutorial-browser-chrome">
            <span className="tutorial-browser-dot" />
            <span className="tutorial-browser-dot" />
            <span className="tutorial-browser-dot" />
            <span className="tutorial-browser-url" />
          </div>
          <div className="tutorial-browser-content">
            <div className="tutorial-browser-toolbar">
              <span className="tutorial-browser-wave" />
              <span className="tutorial-browser-wave" />
              <span className="tutorial-browser-wave" />
              <span className="tutorial-browser-wave" />
              <span className="tutorial-browser-wave" />
            </div>
            <motion.div
              className="tutorial-browser-pwa"
              initial={reduce ? false : { y: 6, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{
                type: 'spring',
                stiffness: 420,
                damping: 24,
                delay: reduce ? 0 : 0.15,
              }}
            >
              <Icon name="install" size={14} />
              <span>PWA</span>
            </motion.div>
            <motion.div
              className="tutorial-browser-notify"
              initial={reduce ? false : { x: 8, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{
                type: 'spring',
                stiffness: 380,
                damping: 22,
                delay: reduce ? 0 : 0.32,
              }}
            >
              <Icon name="bell" size={13} />
              <span className="tutorial-browser-notify-bars">
                <span />
                <span />
                <span />
              </span>
            </motion.div>
            <motion.div
              className="tutorial-browser-lock"
              animate={
                reduce
                  ? { opacity: 0.5 }
                  : { opacity: [0.35, 0.75, 0.35] }
              }
              transition={{
                duration: 2.2,
                repeat: reduce ? 0 : Infinity,
                ease: 'easeInOut',
              }}
            >
              <Icon name="lock" size={16} />
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  )
}
