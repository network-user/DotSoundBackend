import { motion } from 'framer-motion'
import { useReducedMotion } from '@/lib/motion'

export function RadioPage() {
  const reduce = useReducedMotion()
  return (
    <div className="tutorial-illustration tutorial-illustration-radio">
      <span className="tutorial-radio-logo" aria-hidden>
        .звук
      </span>
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="tutorial-radio-wave"
          initial={{ scale: 0.6, opacity: 0 }}
          animate={
            reduce
              ? { scale: 1, opacity: 0.2 }
              : {
                  scale: [0.6, 1.6],
                  opacity: [0.5, 0],
                }
          }
          transition={{
            duration: 2.6,
            repeat: Infinity,
            delay: i * 0.7,
            ease: 'easeOut',
          }}
          aria-hidden
        />
      ))}
    </div>
  )
}
