import {
  type RefObject,
  useEffect,
} from 'react'

const DRAG_THRESHOLD_PX = 6

function isExcludedDragTarget(target: EventTarget | null): boolean {
  const t = target as HTMLElement | null
  if (!t) return true
  if (t.closest('a[href], input, textarea, select')) {
    return true
  }
  if (t.closest('.track-card-actions')) {
    return true
  }
  return false
}

/**
 * Mouse drag-to-scroll for horizontal overflow containers (desktop).
 * Touch keeps native pan-x; does not run for pen/touch pointers.
 */
export function useHorizontalPointerDragScroll(
  ref: RefObject<HTMLElement | null>,
  enabled: boolean,
  resetKey: number,
): void {
  useEffect(() => {
    if (!enabled) return
    const el = ref.current
    if (!el) return

    let activeId: number | null = null
    let startX = 0
    let startScroll = 0
    let dragging = false

    const onDown = (e: PointerEvent) => {
      if (e.pointerType !== 'mouse') return
      if (e.button !== 0) return
      if (isExcludedDragTarget(e.target)) return
      activeId = e.pointerId
      startX = e.clientX
      startScroll = el.scrollLeft
      dragging = false
      try {
        el.setPointerCapture(e.pointerId)
      } catch {
        /* ignore */
      }
    }

    const onMove = (e: PointerEvent) => {
      if (activeId !== e.pointerId) return
      const dx = e.clientX - startX
      if (!dragging && Math.abs(dx) > DRAG_THRESHOLD_PX) {
        dragging = true
        el.classList.add('rf-drag-scroll--active')
      }
      if (dragging) {
        el.scrollLeft = startScroll - dx
        e.preventDefault()
      }
    }

    const onEnd = (e: PointerEvent) => {
      if (activeId !== e.pointerId) return
      activeId = null
      el.classList.remove('rf-drag-scroll--active')
      try {
        el.releasePointerCapture(e.pointerId)
      } catch {
        /* ignore */
      }
      if (dragging) {
        dragging = false
        const block = (ev: Event) => {
          ev.preventDefault()
          ev.stopPropagation()
        }
        el.addEventListener('click', block, {
          capture: true,
          once: true,
        })
      }
    }

    el.addEventListener('pointerdown', onDown)
    el.addEventListener('pointermove', onMove, {
      passive: false,
    })
    el.addEventListener('pointerup', onEnd)
    el.addEventListener('pointercancel', onEnd)
    return () => {
      el.removeEventListener('pointerdown', onDown)
      el.removeEventListener('pointermove', onMove)
      el.removeEventListener('pointerup', onEnd)
      el.removeEventListener('pointercancel', onEnd)
      el.classList.remove('rf-drag-scroll--active')
    }
  }, [enabled, resetKey])
}
