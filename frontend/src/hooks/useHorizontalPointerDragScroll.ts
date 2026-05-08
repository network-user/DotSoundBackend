import {
  type RefObject,
  useEffect,
} from 'react'

import {
  cancelHorizontalScrollAnimation,
  HORIZONTAL_PAGE_SCROLL_MS,
  snapHorizontalScrollerToNearestPage,
} from '@/lib/horizontalScrollAnimate'
import { useReducedMotion } from '@/lib/motion'

const DRAG_THRESHOLD_PX = 5
const WHEEL_SNAP_DEBOUNCE_MS = 160

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
 * Desktop horizontal scroll: mouse `pointerdown` (capture on scroller) +
 * `pointermove` / `pointerup` on `window`, and horizontal / Shift+wheel.
 * After drag or wheel idle, snaps to the nearest full-width page with
 * rAF animation (WebView-safe). Touch keeps native pan-x.
 */
export function useHorizontalPointerDragScroll(
  ref: RefObject<HTMLElement | null>,
  enabled: boolean,
  resetKey: number,
): void {
  const reduce = useReducedMotion()

  useEffect(() => {
    if (!enabled) return
    const el = ref.current
    if (!el) return

    let wheelSnapTimer: ReturnType<
      typeof setTimeout
    > | null = null

    const scheduleWheelSnap = () => {
      if (wheelSnapTimer !== null) {
        clearTimeout(wheelSnapTimer)
      }
      wheelSnapTimer = setTimeout(() => {
        wheelSnapTimer = null
        snapHorizontalScrollerToNearestPage(el, {
          durationMs: HORIZONTAL_PAGE_SCROLL_MS,
          instant: Boolean(reduce),
        })
      }, WHEEL_SNAP_DEBOUNCE_MS)
    }

    const onPointerDownCapture = (e: PointerEvent) => {
      if (e.pointerType !== 'mouse') return
      if (e.button !== 0) return
      if (!el.contains(e.target as Node)) return
      if (isExcludedDragTarget(e.target)) return

      cancelHorizontalScrollAnimation(el)

      const pid = e.pointerId
      const startX = e.clientX
      const startScroll = el.scrollLeft
      let dragging = false
      let didDrag = false

      const onMove = (ev: PointerEvent) => {
        if (ev.pointerId !== pid) return
        const dx = ev.clientX - startX
        if (!dragging && Math.abs(dx) > DRAG_THRESHOLD_PX) {
          dragging = true
          didDrag = true
          el.classList.add('rf-drag-scroll--active')
        }
        if (dragging) {
          ev.preventDefault()
          el.scrollLeft = startScroll - dx
        }
      }

      const onUp = (ev: PointerEvent) => {
        if (ev.pointerId !== pid) return
        window.removeEventListener('pointermove', onMove, true)
        window.removeEventListener('pointerup', onUp, true)
        window.removeEventListener('pointercancel', onUp, true)
        el.classList.remove('rf-drag-scroll--active')
        if (didDrag) {
          snapHorizontalScrollerToNearestPage(el, {
            durationMs: HORIZONTAL_PAGE_SCROLL_MS,
            instant: Boolean(reduce),
          })
          const kill = (ce: MouseEvent) => {
            ce.preventDefault()
            ce.stopPropagation()
            ce.stopImmediatePropagation()
          }
          window.addEventListener('click', kill, {
            capture: true,
            once: true,
          })
        }
      }

      window.addEventListener('pointermove', onMove, {
        capture: true,
        passive: false,
      })
      window.addEventListener('pointerup', onUp, true)
      window.addEventListener('pointercancel', onUp, true)
    }

    const onWheel = (e: WheelEvent) => {
      const rawX = e.deltaX
      const rawY = e.deltaY
      const dx =
        Math.abs(rawX) > Math.abs(rawY)
          ? rawX
          : e.shiftKey
            ? rawY
            : 0
      if (dx === 0) return
      if (!el.contains(e.target as Node)) return
      const max = Math.max(
        0,
        el.scrollWidth - el.clientWidth,
      )
      if (max <= 1) return
      e.preventDefault()
      cancelHorizontalScrollAnimation(el)
      el.scrollLeft += dx
      scheduleWheelSnap()
    }

    el.addEventListener('pointerdown', onPointerDownCapture, {
      capture: true,
    })
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => {
      el.removeEventListener('pointerdown', onPointerDownCapture, {
        capture: true,
      })
      el.removeEventListener('wheel', onWheel)
      el.classList.remove('rf-drag-scroll--active')
      cancelHorizontalScrollAnimation(el)
      if (wheelSnapTimer !== null) {
        clearTimeout(wheelSnapTimer)
      }
    }
  }, [enabled, resetKey, reduce])
}
