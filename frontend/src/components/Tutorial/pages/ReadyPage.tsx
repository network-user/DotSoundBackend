import { motion } from 'framer-motion'
import { Icon } from '@/components/Icon/Icon'
import { useReducedMotion } from '@/lib/motion'

export function ReadyPage() {
  const reduce = useReducedMotion()
  return (
    <div className="tutorial-illustration tutorial-illustration-ready">
      <motion.div
        className="tutorial-ready-check"
        initial={reduce ? { scale: 1 } : { scale: 0.4, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{
          type: 'spring',
          stiffness: 360,
          damping: 18,
        }}
        aria-hidden
      >
        <Icon name="check" size={42} />
      </motion.div>
    </div>
  )
}
