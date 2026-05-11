import { motion } from 'framer-motion'
import { useReducedMotion } from '@/lib/motion'

const TILES = [0, 1, 2, 3, 4, 5]

export function MixPage() {
  const reduce = useReducedMotion()
  return (
    <div className="tutorial-illustration tutorial-illustration-mix">
      <div className="tutorial-mix-grid" aria-hidden>
        {TILES.map((i) => (
          <motion.div
            key={i}
            className={`tutorial-mix-tile tutorial-mix-tile--${i}`}
            initial={
              reduce
                ? { opacity: 1, scale: 1 }
                : { opacity: 0, scale: 0.8 }
            }
            animate={{ opacity: 1, scale: 1 }}
            transition={{
              delay: reduce ? 0 : i * 0.12,
              duration: 0.45,
              ease: [0.16, 1, 0.3, 1],
            }}
          />
        ))}
      </div>
    </div>
  )
}
