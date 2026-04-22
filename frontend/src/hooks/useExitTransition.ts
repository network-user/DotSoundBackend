import { useEffect, useRef, useState } from 'react'

interface Result {
  /** True while component should remain mounted. */
  mounted: boolean
  /** True after `open` flips to false, until exit anim ends. */
  closing: boolean
  /** Class string to spread, e.g. `${baseClass}${cls}`. */
  cls: string
}

/**
 * Keeps a modal/sheet mounted while its exit animation runs.
 * Use to gate `if (!mounted) return null` after `open` toggles.
 */
export function useExitTransition(
  open: boolean,
  durationMs: number = 220,
): Result {
  const [mounted, setMounted] = useState(open)
  const [closing, setClosing] = useState(false)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    if (open) {
      setMounted(true)
      setClosing(false)
      if (timer.current) {
        window.clearTimeout(timer.current)
        timer.current = null
      }
      return
    }
    if (!mounted) return
    setClosing(true)
    timer.current = window.setTimeout(() => {
      setMounted(false)
      setClosing(false)
      timer.current = null
    }, durationMs)
    return () => {
      if (timer.current) {
        window.clearTimeout(timer.current)
        timer.current = null
      }
    }
  }, [open, mounted, durationMs])

  return { mounted, closing, cls: closing ? ' is-closing' : '' }
}
