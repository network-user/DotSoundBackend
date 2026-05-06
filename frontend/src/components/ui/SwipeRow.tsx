import {
  type ReactNode,
  useRef,
  useState,
} from 'react'
import {
  m,
  SPRING_GENTLE,
  useReducedMotion,
} from '@/lib/motion'
import {
  type PanInfo,
  useMotionValue,
  useTransform,
} from 'framer-motion'
import { Icon } from '@/components/Icon/Icon'
import { haptic } from '@/lib/telegram'

export interface SwipeAction {
  icon: string
  label: string
  onTrigger: () => void
  destructive?: boolean
}

export interface SwipeRowProps {
  leftAction?: SwipeAction
  rightAction?: SwipeAction
  threshold?: number
  className?: string
  children: ReactNode
}

const MAX_DRAG = 160

export function SwipeRow({
  leftAction,
  rightAction,
  threshold = 80,
  className,
  children,
}: SwipeRowProps) {
  const reduce = useReducedMotion()
  const x = useMotionValue(0)
  const [armed, setArmed] = useState<
    null | 'left' | 'right'
  >(null)
  const armedRef = useRef<null | 'left' | 'right'>(null)

  const leftOpacity = useTransform(
    x,
    [0, threshold * 0.5, threshold],
    [0, 0.6, 1],
  )
  const rightOpacity = useTransform(
    x,
    [-threshold, -threshold * 0.5, 0],
    [1, 0.6, 0],
  )

  const handleDrag = (
    _: unknown,
    info: PanInfo,
  ) => {
    const v = info.offset.x
    let next: null | 'left' | 'right' = null
    if (v > threshold && leftAction) next = 'left'
    else if (v < -threshold && rightAction) next = 'right'
    if (next !== armedRef.current) {
      armedRef.current = next
      setArmed(next)
      if (next) {
        try {
          haptic('light')
        } catch {
          /* ignore */
        }
      }
    }
  }

  const handleEnd = (
    _: unknown,
    info: PanInfo,
  ) => {
    const v = info.offset.x
    if (v > threshold && leftAction) {
      leftAction.onTrigger()
    } else if (v < -threshold && rightAction) {
      rightAction.onTrigger()
    }
    armedRef.current = null
    setArmed(null)
  }

  const dragLeft = leftAction ? -MAX_DRAG : 0
  const dragRight = rightAction ? MAX_DRAG : 0

  if (reduce) {
    return (
      <div className={['swipe-row', className].filter(Boolean).join(' ')}>
        {children}
      </div>
    )
  }

  return (
    <div
      className={[
        'swipe-row',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {leftAction && (
        <m.div
          aria-hidden="true"
          className={[
            'swipe-action',
            'swipe-action-left',
            leftAction.destructive
              ? 'swipe-action--destructive'
              : '',
            armed === 'left'
              ? 'swipe-action--armed'
              : '',
          ]
            .filter(Boolean)
            .join(' ')}
          style={{ opacity: leftOpacity }}
        >
          <Icon name={leftAction.icon} size={20} />
          <span className="swipe-action__label">
            {leftAction.label}
          </span>
        </m.div>
      )}
      {rightAction && (
        <m.div
          aria-hidden="true"
          className={[
            'swipe-action',
            'swipe-action-right',
            rightAction.destructive
              ? 'swipe-action--destructive'
              : '',
            armed === 'right'
              ? 'swipe-action--armed'
              : '',
          ]
            .filter(Boolean)
            .join(' ')}
          style={{ opacity: rightOpacity }}
        >
          <Icon name={rightAction.icon} size={20} />
          <span className="swipe-action__label">
            {rightAction.label}
          </span>
        </m.div>
      )}
      <m.div
        className="swipe-row__content"
        drag="x"
        dragConstraints={{
          left: dragLeft,
          right: dragRight,
        }}
        dragElastic={0.2}
        dragMomentum={false}
        style={{ x }}
        onDrag={handleDrag}
        onDragEnd={handleEnd}
        animate={{ x: 0 }}
        transition={SPRING_GENTLE}
      >
        {children}
      </m.div>
    </div>
  )
}
