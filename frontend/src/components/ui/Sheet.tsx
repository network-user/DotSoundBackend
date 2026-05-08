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
  /**
   * Visual height tier of the sheet:
   *  - 'auto'   — content-driven (legacy default).
   *  - 'medium' — ~72vh, fits over PlayerBar + BottomNav.
   *  - 'tall'   — ~92vh, almost full-screen with safe-area gap on top.
   */
  snap?: 'auto' | 'medium' | 'tall'
}

const EXIT_DURATION_MS = 220
const RUBBERBAND_RANGE = 96

/**
 * Bottom sheet with swipe-down dismissal, Escape support, exit
 * animation and a visible drag handle. Pure transitions — no
 * Framer dep. The drag area covers both the handle strip and
 * any element with `data-sheet-drag` so the user can grab the
 * top of the body, not just the tiny handle bar.
 */
export function Sheet({
  open,
  onClose,
  children,
  ariaLabel,
  swipeThreshold = 100,
  snap = 'auto',
}: Props) {
  const innerRef = useRef<HTMLDivElement>(null)
  const startY = useRef<number | null>(null)
  const offsetY = useRef(0)
  const dragId = useRef<number | null>(null)
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

  const applyOffset = (raw: number) => {
    const clamped = Math.max(0, raw)
    const eased =
      clamped <= RUBBERBAND_RANGE
        ? clamped
        : RUBBERBAND_RANGE +
          (clamped - RUBBERBAND_RANGE) * 0.45
    offsetY.current = eased
    if (innerRef.current) {
      innerRef.current.style.transform = `translateY(${eased}px)`
    }
  }

  const onPointerDown = (
    e: PointerEvent<HTMLDivElement>,
  ) => {
    startY.current = e.clientY
    dragId.current = e.pointerId
    offsetY.current = 0
    if (innerRef.current) {
      innerRef.current.style.transition = 'none'
    }
    try {
      ;(e.target as Element).setPointerCapture?.(
        e.pointerId,
      )
    } catch {
      /* ignore */
    }
  }

  const onPointerMove = (
    e: PointerEvent<HTMLDivElement>,
  ) => {
    if (
      startY.current === null ||
      dragId.current !== e.pointerId
    ) {
      return
    }
    const delta = e.clientY - startY.current
    applyOffset(delta)
  }

  const onPointerUp = (
    e?: PointerEvent<HTMLDivElement>,
  ) => {
    if (innerRef.current) {
      innerRef.current.style.transition = ''
      innerRef.current.style.transform = ''
    }
    const traveled = offsetY.current
    if (e && dragId.current !== null) {
      try {
        ;(e.target as Element).releasePointerCapture?.(
          dragId.current,
        )
      } catch {
        /* ignore */
      }
    }
    if (traveled > swipeThreshold) {
      onClose()
    }
    startY.current = null
    dragId.current = null
    offsetY.current = 0
  }

  const snapClass =
    snap === 'medium'
      ? ' sheet-inner--snap-medium'
      : snap === 'tall'
        ? ' sheet-inner--snap-tall'
        : ''

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
        className={`sheet-inner${closing ? ' is-closing' : ''}${snapClass}`}
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
