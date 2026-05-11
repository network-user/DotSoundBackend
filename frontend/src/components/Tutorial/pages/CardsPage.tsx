import { motion } from 'framer-motion'
import { useReducedMotion } from '@/lib/motion'

const LINES = [88, 72, 92, 64]

export function CardsPage() {
  const reduce = useReducedMotion()
  return (
    <div className="tutorial-illustration tutorial-illustration-cards">
      <div className="tutorial-card-mock" aria-hidden>
        <div className="tutorial-card-cover" />
        <div className="tutorial-card-meta">
          <span className="tutorial-card-title-bar" />
          <span className="tutorial-card-artist-bar" />
        </div>
        <div className="tutorial-card-lyrics">
          {LINES.map((width, i) => (
            <motion.span
              key={i}
              className="tutorial-card-line"
              style={{ width: `${width}%` }}
              initial={reduce ? { opacity: 1 } : { opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{
                delay: reduce ? 0 : 0.2 + i * 0.15,
                duration: 0.4,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
