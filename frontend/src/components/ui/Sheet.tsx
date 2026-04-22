import {
  useEffect,
  useRef,
  useState,
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

const EXIT_DURATION_MS = 220

/**
 * Bottom sheet with swipe-down dismissal, Escape support, exit
 * animation and a visible drag handle. Pure transitions — no
 * Framer dep.
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
  const [mounted, setMounted] = useState(open)
  const [closing, setClosing] = useState(false)
  const closingTimer = useRef<number | null>(null)

  useEffect(() => {
    if (open) {
      setMounted(true)
      setClosing(false)
      if (closingTimer.current) {
        window.clearTimeout(closingTimer.current)
        closingTimer.current = null
      }
      return
    }
    if (!mounted) return
    setClosing(true)
    closingTimer.current = window.setTimeout(() => {
      setMounted(false)
      setClosing(false)
      closingTimer.current = null
    }, EXIT_DURATION_MS)
    return () => {
      if (closingTimer.current) {
        window.clearTimeout(closingTimer.current)
        closingTimer.current = null
      }
    }
  }, [open, mounted])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () =>
      window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!mounted) return null

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
      className={`sheet-backdrop${closing ? ' is-closing' : ''}`}
      role="dialog"
      aria-modal="true"
      aria-label={ariaLabel}
      onClick={onClose}
    >
      <div
        ref={innerRef}
        className={`sheet-inner${closing ? ' is-closing' : ''}`}
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
