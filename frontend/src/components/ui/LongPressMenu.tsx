import {
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence } from 'framer-motion'
import {
  m,
  SPRING_GENTLE,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { Icon } from '@/components/Icon/Icon'
import { haptic } from '@/lib/telegram'

export interface LongPressMenuItem {
  id: string
  label: string
  icon?: string
  onPick: () => void
  destructive?: boolean
}

export interface LongPressMenuProps {
  items: LongPressMenuItem[]
  delayMs?: number
  disabled?: boolean
  children: ReactNode
}

export function LongPressMenu({
  items,
  delayMs = 450,
  disabled = false,
  children,
}: LongPressMenuProps) {
  const reduce = useReducedMotion()
  const [open, setOpen] = useState(false)
  const timer = useRef<ReturnType<
    typeof setTimeout
  > | null>(null)
  const moved = useRef(false)
  const startPoint = useRef<{
    x: number
    y: number
  } | null>(null)

  const clearTimer = () => {
    if (timer.current) {
      clearTimeout(timer.current)
      timer.current = null
    }
  }

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () =>
      document.removeEventListener('keydown', onKey)
  }, [open])

  const onPointerDown = (
    e: React.PointerEvent<HTMLDivElement>,
  ) => {
    if (disabled) return
    if (e.pointerType === 'mouse' && e.button !== 0) {
      return
    }
    moved.current = false
    startPoint.current = {
      x: e.clientX,
      y: e.clientY,
    }
    clearTimer()
    timer.current = setTimeout(() => {
      if (moved.current) return
      try {
        haptic('medium')
      } catch {
        /* ignore */
      }
      setOpen(true)
    }, delayMs)
  }

  const onPointerMove = (
    e: React.PointerEvent<HTMLDivElement>,
  ) => {
    if (!startPoint.current) return
    const dx = e.clientX - startPoint.current.x
    const dy = e.clientY - startPoint.current.y
    if (Math.hypot(dx, dy) > 8) {
      moved.current = true
      clearTimer()
    }
  }

  const onPointerUp = () => {
    clearTimer()
    startPoint.current = null
  }

  const onContextMenu = (
    e: React.MouseEvent<HTMLDivElement>,
  ) => {
    if (disabled) return
    e.preventDefault()
    setOpen(true)
  }

  const handlePick = (item: LongPressMenuItem) => {
    setOpen(false)
    try {
      haptic('light')
    } catch {
      /* ignore */
    }
    item.onPick()
  }

  const overlay =
    typeof document !== 'undefined' ? (
      <AnimatePresence>
        {open && (
          <m.div
            key="lpm-overlay"
            className="long-press-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={TWEEN_FAST}
            onPointerDown={(e) => {
              if (e.target === e.currentTarget) {
                e.preventDefault()
                setOpen(false)
              }
            }}
            onClick={() => setOpen(false)}
            role="presentation"
          >
            <m.div
              className="long-press-card"
              initial={
                reduce
                  ? { opacity: 0 }
                  : { opacity: 0, scale: 0.92, y: 8 }
              }
              animate={
                reduce
                  ? { opacity: 1 }
                  : { opacity: 1, scale: 1, y: 0 }
              }
              exit={
                reduce
                  ? { opacity: 0 }
                  : { opacity: 0, scale: 0.96, y: 6 }
              }
              transition={
                reduce ? TWEEN_FAST : SPRING_GENTLE
              }
              role="menu"
              onPointerDown={(e) =>
                e.stopPropagation()
              }
              onClick={(e) => e.stopPropagation()}
            >
              {items.map((it) => (
                <button
                  key={it.id}
                  type="button"
                  role="menuitem"
                  className={[
                    'long-press-item',
                    it.destructive
                      ? 'long-press-item--destructive'
                      : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => handlePick(it)}
                >
                  <span className="long-press-item__label">
                    {it.label}
                  </span>
                  {it.icon && (
                    <Icon
                      name={it.icon}
                      size={18}
                    />
                  )}
                </button>
              ))}
            </m.div>
          </m.div>
        )}
      </AnimatePresence>
    ) : null

  return (
    <>
      <div
        className="long-press-trigger"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onContextMenu={onContextMenu}
      >
        {children}
      </div>
      {overlay
        ? createPortal(overlay, document.body)
        : null}
    </>
  )
}
