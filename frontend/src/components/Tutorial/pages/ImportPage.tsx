import { motion } from 'framer-motion'
import { Icon } from '@/components/Icon/Icon'
import { useReducedMotion } from '@/lib/motion'

const ROWS = [0, 1, 2, 3]

export function ImportPage() {
  const reduce = useReducedMotion()
  return (
    <div className="tutorial-illustration tutorial-illustration-import">
      <div className="tutorial-import-stack" aria-hidden>
        {ROWS.map((i) => (
          <motion.div
            key={i}
            className="tutorial-import-row"
            initial={
              reduce
                ? { opacity: 1, x: 0 }
                : { opacity: 0, x: -24 }
            }
            animate={{ opacity: 1, x: 0 }}
            transition={{
              delay: reduce ? 0 : i * 0.18,
              duration: 0.5,
              ease: [0.16, 1, 0.3, 1],
            }}
          >
            <span className="tutorial-import-dot" />
            <span className="tutorial-import-bar" />
          </motion.div>
        ))}
      </div>
      <motion.div
        className="tutorial-import-plus"
        initial={reduce ? { scale: 1 } : { scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: reduce ? 0 : 0.8, duration: 0.4 }}
        aria-hidden
      >
        <Icon name="plus" size={22} />
      </motion.div>
    </div>
  )
}
