import { motion } from 'framer-motion'
import { useReducedMotion } from '@/lib/motion'

const CARDS = [
  { offsetX: -24, offsetY: 12, rotate: -6, delay: 0 },
  { offsetX: 0, offsetY: 0, rotate: 0, delay: 0.1 },
  { offsetX: 24, offsetY: -12, rotate: 6, delay: 0.2 },
]

export function MixPage() {
  const reduce = useReducedMotion()
  return (
    <div className="tutorial-illustration tutorial-illustration-mix">
      <div className="tutorial-mix-stack" aria-hidden>
        {CARDS.map((c, i) => (
          <motion.div
            key={i}
            className={`tutorial-mix-card tutorial-mix-card--${i}`}
            initial={
              reduce
                ? {
                    opacity: 1,
                    x: c.offsetX,
                    y: c.offsetY,
                    rotate: c.rotate,
                  }
                : {
                    opacity: 0,
                    x: c.offsetX,
                    y: c.offsetY + 20,
                    rotate: c.rotate,
                  }
            }
            animate={{
              opacity: 1,
              x: c.offsetX,
              y: c.offsetY,
              rotate: c.rotate,
            }}
            transition={{
              delay: reduce ? 0 : c.delay,
              duration: 0.55,
              ease: [0.16, 1, 0.3, 1],
            }}
          >
            <span className="tutorial-mix-card-cover" />
            <span className="tutorial-mix-card-bar" />
            <span className="tutorial-mix-card-bar tutorial-mix-card-bar--short" />
          </motion.div>
        ))}
        <motion.span
          className="tutorial-mix-pulse"
          initial={{ scale: 0.6, opacity: 0 }}
          animate={
            reduce
              ? { scale: 1, opacity: 0.3 }
              : {
                  scale: [0.6, 1.2, 0.6],
                  opacity: [0.5, 0.1, 0.5],
                }
          }
          transition={{
            duration: 2.4,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: reduce ? 0 : 0.4,
          }}
          aria-hidden
        />
      </div>
    </div>
  )
}
