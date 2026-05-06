import { useEffect, useRef, useState } from 'react'

interface UsePullToRefreshOpts {
  /**
   * Element id of the scrollable container. Defaults to `main` —
   * the Mini App's primary scroll surface.
   */
  containerId?: string
  /**
   * Pixel distance the user has to drag past the top before the
   * refresh fires when they release.
   */
  triggerDistance?: number
  /**
   * Called when the user releases past the threshold. Returns a
   * promise we await before clearing the spinner state.
   */
  onRefresh: () => Promise<unknown> | void
  /**
   * If false, the hook is inert. Use this to scope pull-to-refresh
   * to the active view only.
   */
  enabled?: boolean
}

interface State {
  pulling: boolean
  distance: number
  refreshing: boolean
}

/**
 * Native-feeling pull-to-refresh on the Mini App scroll container.
 * Works with touch only (mobile / Telegram Mini App). Desktop is
 * unaffected.
 */
export function usePullToRefresh(
  opts: UsePullToRefreshOpts,
): State {
  const {
    containerId = 'main',
    triggerDistance = 70,
    onRefresh,
    enabled = true,
  } = opts
  const [state, setState] = useState<State>({
    pulling: false,
    distance: 0,
    refreshing: false,
  })
  const startYRef = useRef<number | null>(null)
  const distRef = useRef(0)

  useEffect(() => {
    if (!enabled) return
    const el = document.getElementById(containerId)
    if (!el) return

    const onTouchStart = (e: TouchEvent) => {
      if (state.refreshing) return
      if (el.scrollTop > 0) {
        startYRef.current = null
        return
      }
      startYRef.current = e.touches[0].clientY
      distRef.current = 0
    }

    const onTouchMove = (e: TouchEvent) => {
      if (state.refreshing) return
      if (startYRef.current == null) return
      if (el.scrollTop > 0) {
        startYRef.current = null
        if (state.pulling) {
          setState((s) => ({
            ...s,
            pulling: false,
            distance: 0,
          }))
        }
        return
      }
      const dy = e.touches[0].clientY - startYRef.current
      if (dy <= 0) return
      const damped = Math.min(140, dy * 0.55)
      distRef.current = damped
      if (damped > 4) {
        e.preventDefault()
        setState((s) => ({
          ...s,
          pulling: true,
          distance: damped,
        }))
      }
    }

    const onTouchEnd = () => {
      if (state.refreshing) return
      const final = distRef.current
      startYRef.current = null
      distRef.current = 0
      if (final >= triggerDistance) {
        setState({
          pulling: false,
          distance: 0,
          refreshing: true,
        })
        Promise.resolve(onRefresh())
          .catch(() => {})
          .finally(() => {
            setState({
              pulling: false,
              distance: 0,
              refreshing: false,
            })
          })
      } else {
        setState((s) => ({
          ...s,
          pulling: false,
          distance: 0,
        }))
      }
    }

    el.addEventListener('touchstart', onTouchStart, {
      passive: true,
    })
    el.addEventListener('touchmove', onTouchMove, {
      passive: false,
    })
    el.addEventListener('touchend', onTouchEnd)
    el.addEventListener('touchcancel', onTouchEnd)
    return () => {
      el.removeEventListener('touchstart', onTouchStart)
      el.removeEventListener('touchmove', onTouchMove)
      el.removeEventListener('touchend', onTouchEnd)
      el.removeEventListener('touchcancel', onTouchEnd)
    }
  }, [
    containerId,
    triggerDistance,
    onRefresh,
    enabled,
    state.refreshing,
    state.pulling,
  ])

  return state
}
