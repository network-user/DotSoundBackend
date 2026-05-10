import { type ReactNode, useEffect, useRef } from 'react'
import { useReducedMotion } from '@/lib/motion'

interface RippleRing {
  born: number
}

export interface AudioRippleProps {
  bpm?: number
  active?: boolean
  getAnalyser?: () => AnalyserNode | null
  className?: string
  children: ReactNode
}

const BASS_BINS = 4
const BEAT_THRESHOLD = 0.50
const BEAT_COOLDOWN_MS = 320
const RING_DURATION_MS = 860

export function AudioRipple({
  bpm = 120,
  active = true,
  getAnalyser,
  className,
  children,
}: AudioRippleProps) {
  const reduce = useReducedMotion()
  const spanRef = useRef<HTMLSpanElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const ringsRef = useRef<RippleRing[]>([])
  const lastBeatRef = useRef<number>(0)
  const rafRef = useRef<number | null>(null)
  const startRef = useRef<number>(performance.now())
  const fpsGateRef = useRef<number>(0)

  useEffect(() => {
    const span = spanRef.current
    if (!span) return

    if (reduce || !active) {
      span.style.setProperty('--bp-phase', '0')
      return
    }

    const periodMs = 60000 / Math.max(40, Math.min(220, bpm))
    const freqData = new Uint8Array(128)
    let stopped = false

    const tick = (now: number) => {
      if (stopped) return

      const analyser = getAnalyser?.() ?? null
      const canvas = canvasRef.current
      let phase: number

      if (analyser) {
        analyser.getByteFrequencyData(freqData)
        let sum = 0
        for (let i = 0; i < BASS_BINS; i++) sum += freqData[i]
        const energy = sum / (BASS_BINS * 255)

        phase = Math.min(1, energy)

        if (canvas && energy > BEAT_THRESHOLD && now - lastBeatRef.current > BEAT_COOLDOWN_MS) {
          lastBeatRef.current = now
          ringsRef.current.push({ born: now })
        }
      } else {
        // BPM-based fallback at ~20 fps
        if (now - fpsGateRef.current < 50) {
          rafRef.current = requestAnimationFrame(tick)
          return
        }
        fpsGateRef.current = now
        const elapsed = now - startRef.current
        phase = Math.abs(Math.sin((elapsed / periodMs) * Math.PI))
      }

      span.style.setProperty('--bp-phase', phase.toFixed(3))

      // Draw ripple rings
      if (canvas && ringsRef.current.length > 0) {
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.clearRect(0, 0, canvas.width, canvas.height)
          const cx = canvas.width / 2
          const cy = canvas.height / 2
          // discR in canvas units ≈ half the span width
          // canvas.width = span.offsetWidth * 2, so discR = span.offsetWidth / 2
          const discR = canvas.width / 4

          ringsRef.current = ringsRef.current.filter((ring) => {
            const age = now - ring.born
            if (age >= RING_DURATION_MS) return false
            const progress = age / RING_DURATION_MS
            // Start at disc edge, expand 85% of disc-radius beyond it
            const r = discR + discR * 0.85 * progress
            const alpha = (1 - progress) * 0.55

            ctx.beginPath()
            ctx.arc(cx, cy, r, 0, Math.PI * 2)
            ctx.strokeStyle = `rgba(255,255,255,${alpha.toFixed(3)})`
            ctx.lineWidth = Math.max(0.5, 2.5 - progress * 2)
            ctx.stroke()
            return true
          })
        }
      } else if (canvas && ringsRef.current.length === 0) {
        const ctx = canvas.getContext('2d')
        ctx?.clearRect(0, 0, canvas.width, canvas.height)
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
      span.style.setProperty('--bp-phase', '0')
    }
  }, [bpm, active, getAnalyser, reduce])

  // Keep canvas pixel size in sync with span layout size
  useEffect(() => {
    const span = spanRef.current
    const canvas = canvasRef.current
    if (!span || !canvas) return
    const sync = () => {
      canvas.width = span.offsetWidth * 2
      canvas.height = span.offsetHeight * 2
    }
    const obs = new ResizeObserver(sync)
    obs.observe(span)
    sync()
    return () => obs.disconnect()
  }, [])

  return (
    <span
      ref={spanRef}
      data-beat-active={active && !reduce ? 'true' : 'false'}
      className={['beat-pulse-target', className].filter(Boolean).join(' ')}
      style={
        {
          position: 'relative',
          zIndex: 0,
          ['--bp-phase' as string]: '0',
        } as React.CSSProperties
      }
    >
      {children}
      {active && !reduce && (
        <canvas
          ref={canvasRef}
          aria-hidden
          style={{
            position: 'absolute',
            top: '-50%',
            left: '-50%',
            width: '200%',
            height: '200%',
            pointerEvents: 'none',
            zIndex: -1,
          }}
        />
      )}
    </span>
  )
}
