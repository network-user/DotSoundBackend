import {
  forwardRef,
  useEffect,
  useState,
  useSyncExternalStore,
} from 'react'
import { AnimatePresence } from 'framer-motion'
import {
  m,
  SPRING_GENTLE,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import {
  type IslandEntry,
  dismissIsland,
  getIslandSnapshot,
  subscribeIsland,
} from '@/lib/island'
import { Icon } from '@/components/Icon/Icon'

function useIslandQueue(): IslandEntry[] {
  return useSyncExternalStore(
    subscribeIsland,
    getIslandSnapshot,
    getIslandSnapshot,
  )
}

interface PillProps {
  entry: IslandEntry
}

const IslandPill = forwardRef<HTMLButtonElement, PillProps>(
  function IslandPill({ entry }, ref) {
  const reduce = useReducedMotion()
  const [progress, setProgress] = useState(
    entry.progress ?? 0,
  )
  useEffect(() => {
    setProgress(entry.progress ?? 0)
  }, [entry.progress])

  const isProgress = entry.kind === 'progress'

  const handleClick = () => {
    if (entry.onClick) {
      entry.onClick()
    } else if (entry.kind === 'toast') {
      dismissIsland(entry.id)
    }
  }

  return (
    <m.button
      ref={ref}
      type="button"
      layout
      className={[
        'island',
        `island--${entry.kind}`,
      ].join(' ')}
      onClick={handleClick}
      initial={
        reduce
          ? { opacity: 0 }
          : { opacity: 0, y: -16, scale: 0.92 }
      }
      animate={
        reduce
          ? { opacity: 1 }
          : { opacity: 1, y: 0, scale: 1 }
      }
      exit={
        reduce
          ? { opacity: 0 }
          : { opacity: 0, y: -10, scale: 0.96 }
      }
      transition={reduce ? TWEEN_FAST : SPRING_GENTLE}
    >
      {entry.iconName && (
        <span className="island__icon">
          <Icon name={entry.iconName} size={16} />
        </span>
      )}
      <span className="island__body">
        <span className="island__title">
          {entry.title}
        </span>
        {entry.hint && (
          <span className="island__hint">
            {entry.hint}
          </span>
        )}
      </span>
      {isProgress && (
        <span
          className="island__progress"
          aria-hidden="true"
        >
          <span
            className="island__progress-fill"
            style={{
              width: `${Math.max(0, Math.min(1, progress)) * 100}%`,
            }}
          />
        </span>
      )}
    </m.button>
  )
})

export function DynamicIslandHost() {
  const queue = useIslandQueue()
  const visible = queue.slice(-1)
  return (
    <div className="island-host" aria-live="polite">
      <AnimatePresence mode="popLayout" initial={false}>
        {visible.map((entry) => (
          <IslandPill key={entry.id} entry={entry} />
        ))}
      </AnimatePresence>
    </div>
  )
}

export const DynamicIsland = DynamicIslandHost
