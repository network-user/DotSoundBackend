import {
  type ReactNode,
  useEffect,
  useRef,
} from 'react'
import { useReducedMotion } from '@/lib/motion'

export interface BeatPulseProps {
  bpm?: number
  active?: boolean
  className?: string
  children: ReactNode
}

export function BeatPulse({
  bpm = 120,
  active = true,
  className,
  children,
}: BeatPulseProps) {
  const reduce = useReducedMotion()
  const ref = useRef<HTMLSpanElement | null>(null)
  const startRef = useRef<number>(
    typeof performance !== 'undefined'
      ? performance.now()
      : Date.now(),
  )
  const rafRef = useRef<number | null>(null)
  const lastPaintRef = useRef<number>(0)

  useEffect(() => {
    if (reduce || !active) {
      if (ref.current) {
        ref.current.style.setProperty(
          '--bp-phase',
          '0',
        )
      }
      return
    }
    const periodMs = 60000 / Math.max(40, Math.min(220, bpm))
    let stopped = false
    const targetFrameMs = 1000 / 20

    const tick = (t: number) => {
      if (stopped) return
      if (t - lastPaintRef.current < targetFrameMs) {
        rafRef.current = requestAnimationFrame(tick)
        return
      }
      lastPaintRef.current = t
      const elapsed = t - startRef.current
      const phase =
        Math.abs(
          Math.sin((elapsed / periodMs) * Math.PI),
        )
      if (ref.current) {
        ref.current.style.setProperty(
          '--bp-phase',
          phase.toFixed(3),
        )
      }
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => {
      stopped = true
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }
  }, [bpm, active, reduce])

  return (
    <span
      ref={ref}
      className={[
        'beat-pulse-target',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      style={{
        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
        ['--bp-phase' as string]: '0',
      } as React.CSSProperties}
    >
      {children}
    </span>
  )
}
