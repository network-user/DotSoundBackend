import { motion } from 'framer-motion'
import { useReducedMotion } from '@/lib/motion'

export function SwipesPage() {
  const reduce = useReducedMotion()
  return (
    <div className="tutorial-illustration tutorial-illustration-swipes">
      <motion.div
        className="tutorial-swipe-card"
        animate={
          reduce
            ? { x: 0, rotate: 0 }
            : {
                x: [0, 90, 0, -90, 0],
                rotate: [0, 8, 0, -8, 0],
              }
        }
        transition={{
          duration: 4.2,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        aria-hidden
      >
        <span className="tutorial-swipe-badge tutorial-swipe-badge--like">
          LIKE
        </span>
        <span className="tutorial-swipe-badge tutorial-swipe-badge--nope">
          NOPE
        </span>
        <div className="tutorial-swipe-cover" />
        <div className="tutorial-swipe-bar" />
        <div className="tutorial-swipe-bar tutorial-swipe-bar--short" />
      </motion.div>
    </div>
  )
}
