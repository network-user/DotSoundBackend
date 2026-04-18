import {
  useEffect,
  useRef,
  type PointerEvent,
  type ReactNode,
} from 'react'

interface Props {
  open: boolean
  onClose: () => void
  children: ReactNode
  ariaLabel?: string
  /** Distance in px the user has to drag to dismiss. */
  swipeThreshold?: number
}

/**
 * Bottom sheet with swipe-down dismissal, Escape support and
 * a visible drag handle. Pure transitions — no Framer dep.
 */
export function Sheet({
  open,
  onClose,
  children,
  ariaLabel,
  swipeThreshold = 100,
}: Props) {
  const innerRef = useRef<HTMLDivElement>(null)
  const startY = useRef<number | null>(null)
  const offsetY = useRef(0)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () =>
      window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const onPointerDown = (
    e: PointerEvent<HTMLDivElement>,
  ) => {
    startY.current = e.clientY
    offsetY.current = 0
  }

  const onPointerMove = (
    e: PointerEvent<HTMLDivElement>,
  ) => {
    if (startY.current === null) return
    const delta = e.clientY - startY.current
    offsetY.current = Math.max(0, delta)
    if (innerRef.current) {
      innerRef.current.style.transform = `translateY(${offsetY.current}px)`
    }
  }

  const onPointerUp = () => {
    if (innerRef.current) {
      innerRef.current.style.transform = ''
    }
    if (offsetY.current > swipeThreshold) {
      onClose()
    }
    startY.current = null
    offsetY.current = 0
  }

  return (
    <div
      className="sheet-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={ariaLabel}
      onClick={onClose}
    >
      <div
        ref={innerRef}
        className="sheet-inner"
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="sheet-handle-zone"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          <div className="sheet-handle" />
        </div>
        <div className="sheet-content">
          {children}
        </div>
      </div>
    </div>
  )
}
