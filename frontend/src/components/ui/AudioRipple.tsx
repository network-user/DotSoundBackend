import { type ReactNode, useEffect, useRef } from 'react'
import { useReducedMotion } from '@/lib/motion'

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
const RING_DURATION_MS = 860
const BEAT_MULTIPLIER = 1.4
const MIN_BEAT_ENERGY = 0.12
const HISTORY_SIZE = 120

function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha.toFixed(3)})`
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
  const spanRef = useRef<HTMLSpanElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const ringsRef = useRef<RippleRing[]>([])
  const lastBeatRef = useRef<number>(0)
  const rafRef = useRef<number | null>(null)
  const startRef = useRef<number>(performance.now())
  const fpsGateRef = useRef<number>(0)

  // Adaptive beat detection: circular buffer of energy history
  const energyHistoryRef = useRef<Float32Array>(
    new Float32Array(HISTORY_SIZE),
  )
  const energyIdxRef = useRef<number>(0)
  const energySumRef = useRef<number>(0)

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

        // Update rolling average
        const oldest =
          energyHistoryRef.current[energyIdxRef.current]!
        energySumRef.current += energy - oldest
        energyHistoryRef.current[energyIdxRef.current] = energy
        energyIdxRef.current =
          (energyIdxRef.current + 1) % HISTORY_SIZE
        const avgEnergy = energySumRef.current / HISTORY_SIZE

        phase = Math.min(1, energy)

        // Adaptive beat: energy exceeds running average by multiplier
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
      if (canvas) {
        if (ringsRef.current.length > 0) {
          const ctx = canvas.getContext('2d')
          if (ctx) {
            ctx.clearRect(0, 0, canvas.width, canvas.height)
            const cx = canvas.width / 2
            const cy = canvas.height / 2
            const discR = canvas.width / 4

            ringsRef.current = ringsRef.current.filter((ring) => {
              const age = now - ring.born
              if (age >= RING_DURATION_MS) return false
              const progress = age / RING_DURATION_MS
              const r = discR + discR * 0.85 * progress
              const alpha = (1 - progress) * 0.55

              ctx.beginPath()
              ctx.arc(cx, cy, r, 0, Math.PI * 2)
              ctx.strokeStyle = ringColor
                ? hexToRgba(ringColor, alpha)
                : `rgba(255,255,255,${alpha.toFixed(3)})`
              ctx.lineWidth = Math.max(0.5, 2.5 - progress * 2)
              ctx.stroke()
              return true
            })
          }
        } else {
          const ctx = canvas.getContext('2d')
          ctx?.clearRect(0, 0, canvas.width, canvas.height)
        }
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
      // Reset adaptive state so next activation starts fresh
      energyHistoryRef.current.fill(0)
      energySumRef.current = 0
      energyIdxRef.current = 0
      span.style.setProperty('--bp-phase', '0')
    }
  }, [bpm, active, getAnalyser, ringColor, reduce])

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
