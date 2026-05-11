import { motion } from 'framer-motion'
import { useReducedMotion } from '@/lib/motion'

export function RadioPage() {
  const reduce = useReducedMotion()
  return (
    <div className="tutorial-illustration tutorial-illustration-radio">
      <motion.div
        className="tutorial-radio-disk"
        animate={
          reduce
            ? { rotate: 0 }
            : { rotate: 360 }
        }
        transition={{
          duration: 14,
          repeat: Infinity,
          ease: 'linear',
        }}
        aria-hidden
      >
        <div className="tutorial-radio-label">.звук</div>
      </motion.div>
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="tutorial-radio-wave"
          initial={{ scale: 0.8, opacity: 0.0 }}
          animate={
            reduce
              ? { scale: 1, opacity: 0.2 }
              : {
                  scale: [0.8, 1.4],
                  opacity: [0.45, 0],
                }
          }
          transition={{
            duration: 2.4,
            repeat: Infinity,
            delay: i * 0.6,
            ease: 'easeOut',
          }}
          aria-hidden
        />
      ))}
    </div>
  )
}
