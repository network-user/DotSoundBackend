import { useCallback, useRef } from 'react'
import type { PointerEvent } from 'react'

interface Options {
  onSwipeLeft?: () => void
  onSwipeRight?: () => void
  threshold?: number
  disabled?: boolean
}

export function useSwipeX({
  onSwipeLeft,
  onSwipeRight,
  threshold = 60,
  disabled = false,
}: Options) {
  const startRef = useRef<{ x: number; y: number } | null>(
    null,
  )

  const onPointerDown = useCallback(
    (e: PointerEvent) => {
      if (disabled) return
      startRef.current = { x: e.clientX, y: e.clientY }
    },
    [disabled],
  )

  const onPointerUp = useCallback(
    (e: PointerEvent) => {
      if (disabled || !startRef.current) return
      const dx = e.clientX - startRef.current.x
      const dy = e.clientY - startRef.current.y
      startRef.current = null
      const absDx = Math.abs(dx)
      const absDy = Math.abs(dy)
      if (absDx > threshold && absDx > absDy * 1.5) {
        e.preventDefault()
        e.stopPropagation()
        if (dx < 0) onSwipeLeft?.()
        else onSwipeRight?.()
      }
    },
    [disabled, threshold, onSwipeLeft, onSwipeRight],
  )

  const onPointerCancel = useCallback(() => {
    startRef.current = null
  }, [])

  return { onPointerDown, onPointerUp, onPointerCancel }
}
