import { useCallback, useRef } from 'react'
import type { PointerEvent } from 'react'

interface Options {
  onSwipeLeft?: () => void
  onSwipeRight?: () => void
  onSwipeUp?: () => void
  onSwipeDown?: () => void
  onProgress?: (dx: number) => void
  threshold?: number
  disabled?: boolean
}

export function useSwipeX({
  onSwipeLeft,
  onSwipeRight,
  onSwipeUp,
  onSwipeDown,
  onProgress,
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

  const onPointerMove = useCallback(
    (e: PointerEvent) => {
      if (disabled || !startRef.current || !onProgress)
        return
      const dx = e.clientX - startRef.current.x
      const dy = e.clientY - startRef.current.y
      if (Math.abs(dx) > Math.abs(dy) * 0.7) {
        onProgress(dx)
      }
    },
    [disabled, onProgress],
  )

  const onPointerUp = useCallback(
    (e: PointerEvent) => {
      if (disabled || !startRef.current) return
      const dx = e.clientX - startRef.current.x
      const dy = e.clientY - startRef.current.y
      startRef.current = null
      onProgress?.(0)
      const absDx = Math.abs(dx)
      const absDy = Math.abs(dy)
      if (absDy > threshold && absDy > absDx * 1.5) {
        e.preventDefault()
        e.stopPropagation()
        if (dy < 0) onSwipeUp?.()
        else onSwipeDown?.()
        return
      }
      if (absDx > threshold && absDx > absDy * 1.5) {
        e.preventDefault()
        e.stopPropagation()
        if (dx < 0) onSwipeLeft?.()
        else onSwipeRight?.()
      }
    },
    [
      disabled,
      threshold,
      onSwipeLeft,
      onSwipeRight,
      onSwipeUp,
      onSwipeDown,
      onProgress,
    ],
  )

  const onPointerCancel = useCallback(() => {
    startRef.current = null
    onProgress?.(0)
  }, [onProgress])

  return {
    onPointerDown,
    onPointerMove,
    onPointerUp,
    onPointerCancel,
  }
}
