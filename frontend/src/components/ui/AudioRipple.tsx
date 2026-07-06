import {
  type CSSProperties,
  type ReactNode,
  useEffect,
  useRef,
} from 'react'
import { useReducedMotion } from '@/lib/motion'
import { isPerfLiteActive } from '@/lib/glassPerformance'

interface RippleRing {
  born: number
}

export interface AudioRippleProps {
  bpm?: number
  active?: boolean
  getAnalyser?: () => AnalyserNode | null
  ringColor?: string
  className?: string
  children: ReactNode
}

const BASS_BINS = 4
const BEAT_COOLDOWN_MS = 320
const RING_DURATION_MS = 980
const BEAT_MULTIPLIER = 1.4
const MIN_BEAT_ENERGY = 0.12
const HISTORY_SIZE = 120
const IDLE_RIPPLE_MS = 2000
const MAX_RINGS = 5

function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha.toFixed(3)})`
}

function ringEase(t: number): number {
  return 1 - (1 - t) ** 2.35
}

export function AudioRipple({
  bpm = 120,
  active = true,
  getAnalyser,
  ringColor,
  className,
  children,
}: AudioRippleProps) {
  const reduce = useReducedMotion()
  const perfLite = isPerfLiteActive()
  const spanRef = useRef<HTMLSpanElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const ringsRef = useRef<RippleRing[]>([])
  const lastBeatRef = useRef<number>(0)
  const lastIdleRippleRef = useRef<number>(0)
  const rafRef = useRef<number | null>(null)
  const startRef = useRef<number>(performance.now())
  const fpsGateRef = useRef<number>(0)

  const energyHistoryRef = useRef<Float32Array>(
    new Float32Array(HISTORY_SIZE),
  )
  const energyIdxRef = useRef<number>(0)
  const energySumRef = useRef<number>(0)

  useEffect(() => {
    const span = spanRef.current
    if (!span) return

    if (reduce || perfLite || !active) {
      span.style.setProperty('--bp-phase', '0')
      return
    }

    const periodMs = 60000 / Math.max(40, Math.min(220, bpm))
    const freqData = new Uint8Array(128)
    let stopped = false

    const tick = (now: number) => {
      if (stopped) return
      // Pause while the tab/webview is backgrounded; visibilitychange
      // resumes the loop.
      if (typeof document !== 'undefined' && document.hidden) {
        rafRef.current = null
        return
      }

      const analyser = getAnalyser?.() ?? null
      const canvas = canvasRef.current
      let phase: number

      if (analyser) {
        // Cap the analyser path to ~30fps (previously uncapped 60fps).
        if (now - fpsGateRef.current < 33) {
          rafRef.current = requestAnimationFrame(tick)
          return
        }
        fpsGateRef.current = now
        analyser.getByteFrequencyData(freqData)
        let sum = 0
        for (let i = 0; i < BASS_BINS; i++) sum += freqData[i]
        const energy = sum / (BASS_BINS * 255)

        const oldest =
          energyHistoryRef.current[energyIdxRef.current]!
        energySumRef.current += energy - oldest
        energyHistoryRef.current[energyIdxRef.current] = energy
        energyIdxRef.current =
          (energyIdxRef.current + 1) % HISTORY_SIZE
        const avgEnergy = energySumRef.current / HISTORY_SIZE

        phase = Math.min(1, energy)

        const beatThreshold = Math.max(
          MIN_BEAT_ENERGY,
          avgEnergy * BEAT_MULTIPLIER,
        )
        if (
          canvas &&
          energy > beatThreshold &&
          now - lastBeatRef.current > BEAT_COOLDOWN_MS
        ) {
          lastBeatRef.current = now
          ringsRef.current.push({ born: now })
        }

        if (
          canvas &&
          ringsRef.current.length < MAX_RINGS &&
          now - lastIdleRippleRef.current > IDLE_RIPPLE_MS
        ) {
          lastIdleRippleRef.current = now
          ringsRef.current.push({ born: now })
        }
      } else {
        if (now - fpsGateRef.current < 50) {
          rafRef.current = requestAnimationFrame(tick)
          return
        }
        fpsGateRef.current = now
        const elapsed = now - startRef.current
        phase = Math.abs(Math.sin((elapsed / periodMs) * Math.PI))

        if (
          canvas &&
          ringsRef.current.length < MAX_RINGS &&
          now - lastIdleRippleRef.current > IDLE_RIPPLE_MS * 1.1
        ) {
          lastIdleRippleRef.current = now
          ringsRef.current.push({ born: now })
        }
      }

      span.style.setProperty('--bp-phase', phase.toFixed(3))

      if (canvas) {
        const ctx = canvas.getContext('2d')
        if (ctx) {
          const dim = canvas.width
          const cx = dim / 2
          const cy = dim / 2
          const baseR = dim * 0.125
          const expand = dim * 0.44
          ctx.clearRect(0, 0, dim, dim)

          ringsRef.current = ringsRef.current.filter((ring) => {
            const age = now - ring.born
            if (age >= RING_DURATION_MS) return false
            const raw = age / RING_DURATION_MS
            const progress = ringEase(raw)
            const r = baseR + expand * progress
            const alpha = (1 - raw) ** 1.05 * 0.52
            const lw = Math.max(0.45, 2.15 * (1 - raw) ** 1.15)
            const stroke = ringColor
              ? hexToRgba(ringColor, alpha * 0.42)
              : `rgba(255,255,255,${(alpha * 0.42).toFixed(3)})`

            ctx.beginPath()
            ctx.arc(cx, cy, r + lw * 0.35, 0, Math.PI * 2)
            ctx.strokeStyle = stroke
            ctx.lineWidth = lw * 0.55
            ctx.stroke()

            ctx.beginPath()
            ctx.arc(cx, cy, r, 0, Math.PI * 2)
            ctx.strokeStyle = ringColor
              ? hexToRgba(ringColor, alpha)
              : `rgba(255,255,255,${alpha.toFixed(3)})`
            ctx.lineWidth = lw
            ctx.stroke()
            return true
          })
        }
      }

      rafRef.current = requestAnimationFrame(tick)
    }

    const onVis = () => {
      if (
        !stopped &&
        !document.hidden &&
        rafRef.current === null
      ) {
        rafRef.current = requestAnimationFrame(tick)
      }
    }
    document.addEventListener('visibilitychange', onVis)
    rafRef.current = requestAnimationFrame(tick)
    return () => {
      stopped = true
      document.removeEventListener('visibilitychange', onVis)
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
      energyHistoryRef.current.fill(0)
      energySumRef.current = 0
      energyIdxRef.current = 0
      ringsRef.current = []
      lastIdleRippleRef.current = 0
      span.style.setProperty('--bp-phase', '0')
    }
  }, [bpm, active, getAnalyser, ringColor, reduce, perfLite])

  // Deps MUST include [active, reduce]: the <canvas> is conditionally
  // rendered (`active && !reduce` below), so each time `active` toggles
  // false→true a fresh DOM node mounts with no inline width/height. If we
  // used [] here, sync() would run only once with whatever canvasRef was
  // at first mount — typically null when isPlaying starts false — and the
  // remounted canvas would stay at its default 300×150 anchored to the
  // span's top-left, which visually looks like ripples drifting off to
  // the right of the cover instead of emanating from its center.
  useEffect(() => {
    const span = spanRef.current
    const canvas = canvasRef.current
    if (!span || !canvas || perfLite) return
    const sync = () => {
      const w = Math.max(1, span.offsetWidth)
      const h = Math.max(1, span.offsetHeight)
      const outer = Math.max(w, h)
      const side = Math.round(outer * 2)
      canvas.width = side
      canvas.height = side
      canvas.style.width = `${outer * 2}px`
      canvas.style.height = `${outer * 2}px`
    }
    const obs = new ResizeObserver(sync)
    obs.observe(span)
    sync()
    return () => obs.disconnect()
  }, [active, reduce, perfLite])

  return (
    <span
      ref={spanRef}
      data-beat-active={active && !reduce && !perfLite ? 'true' : 'false'}
      className={['beat-pulse-target', className].filter(Boolean).join(' ')}
      style={
        {
          position: 'relative',
          zIndex: 0,
          ['--bp-phase' as string]: '0',
        } as CSSProperties
      }
    >
      {children}
      {active && !reduce && !perfLite && (
        <canvas
          ref={canvasRef}
          aria-hidden
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            pointerEvents: 'none',
            zIndex: -1,
          }}
        />
      )}
    </span>
  )
}
