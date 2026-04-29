import {
  useEffect,
  useRef,
  type MutableRefObject,
} from 'react'
import { usePlayerActions, usePlayerState } from '@/store/PlayerContext'

interface Props {
  height?: number
  bars?: number
  className?: string
  /** Softer colors when drawn over the cover art. */
  overlay?: boolean
}

const REDUCED_MOTION_QUERY =
  '(prefers-reduced-motion: reduce)'

const SPECTRUM_INTERVAL_MS = Math.round(1000 / 12)

const MAX_CANVAS_DPR = 1.25

const IDLE_FRAC = 0.18

const MIN_PLAY_FRAC = 0.04

const ATTACK_SMOOTH = 0.56

const DECAY_PER_TICK = 0.26

const DECAY_EASE_MIN = 0.15

const DECAY_EASE_RANGE = 0.85

const DECAY_EASE_POWER = 0.5

const NORM_GAIN = 1.08

const NORM_CURVE_EXP = 0.74

const VISUAL_HEIGHT_CAP = 0.78

const BAR_SPREAD_AMP = 0.068

const BAR_SPREAD_SLOW = 0.042

const DITHER_AMP = 0.014

function shapeLevel(norm: number): number {
  const boosted = Math.min(1, norm * NORM_GAIN)
  const curved = boosted ** NORM_CURVE_EXP
  return curved * VISUAL_HEIGHT_CAP
}

function ditherUnit(barIndex: number, tickMs: number): number {
  const x =
    Math.imul(barIndex + 41, 1597334677) ^
    Math.floor(tickMs * 2.17 + barIndex * 13)
  const u =
    Math.imul(x ^ (x >>> 16), 2246822519) >>> 0
  return u / 4294967296 - 0.5
}

function hash01(i: number): number {
  const x = Math.imul(i + 1, 0x9e3779b9) >>> 0
  return x / 0x1_0000_0000
}

function decaySmoothedTowardIdle(sm: Float32Array, n: number) {
  const maxSpan = 1 - IDLE_FRAC
  for (let i = 0; i < n; i++) {
    const dist = sm[i] - IDLE_FRAC
    if (dist <= 1e-6) {
      sm[i] = IDLE_FRAC
      continue
    }
    if (dist < 0) {
      sm[i] = IDLE_FRAC
      continue
    }
    const distNorm = Math.min(1, dist / maxSpan)
    const ease =
      DECAY_EASE_MIN +
      DECAY_EASE_RANGE * distNorm ** DECAY_EASE_POWER
    const stagger = 0.85 + 0.3 * hash01(i)
    const alpha = DECAY_PER_TICK * ease * stagger
    sm[i] += (IDLE_FRAC - sm[i]) * alpha
  }
}

function ensureSmoothed(
  ref: MutableRefObject<Float32Array | null>,
  n: number,
) {
  if (!ref.current || ref.current.length !== n) {
    ref.current = new Float32Array(n)
    ref.current.fill(IDLE_FRAC)
  }
}

const IDLE_COLOR_EPS = 0.025

function drawBars(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  bars: number,
  heights: Float32Array,
  playColor: string,
  idleColor: string,
  useIdleTint: boolean,
) {
  ctx.clearRect(0, 0, w, h)
  const barW = (w / bars) * 0.64
  const gap = (w / bars) * 0.36
  for (let i = 0; i < bars; i++) {
    const frac = heights[i]
    const bh = Math.max(h * MIN_PLAY_FRAC, frac * h)
    const x = i * (barW + gap) + gap / 2
    const y = (h - bh) / 2
    ctx.fillStyle =
      useIdleTint &&
      frac <= IDLE_FRAC + IDLE_COLOR_EPS
        ? idleColor
        : playColor
    ctx.fillRect(x, y, barW, bh)
  }
}

function drawIdleBars(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  bars: number,
  idleColor: string,
) {
  ctx.clearRect(0, 0, w, h)
  ctx.fillStyle = idleColor
  const barW = (w / bars) * 0.64
  const gap = (w / bars) * 0.36
  for (let i = 0; i < bars; i++) {
    const x = i * (barW + gap) + gap / 2
    const bh = h * IDLE_FRAC
    const y = (h - bh) / 2
    ctx.fillRect(x, y, barW, bh)
  }
}

export function Waveform({
  height = 64,
  bars = 56,
  className,
  overlay = false,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const freqBufRef = useRef<Uint8Array<ArrayBuffer> | null>(
    null,
  )
  const smoothedRef = useRef<Float32Array | null>(null)
  const intervalRef = useRef<number | null>(null)
  const { isPlaying } = usePlayerState()
  const { getAnalyser } = usePlayerActions()

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const reduced = window.matchMedia(
      REDUCED_MOTION_QUERY,
    ).matches
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const idleColor = overlay
      ? 'rgba(255,255,255,0.12)'
      : 'rgba(255,255,255,0.15)'
    const playColor = overlay
      ? 'rgba(255,255,255,0.78)'
      : 'rgba(255,255,255,0.98)'

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      const dpr = Math.min(
        window.devicePixelRatio || 1,
        MAX_CANVAS_DPR,
      )
      canvas.width = Math.floor(rect.width * dpr)
      canvas.height = Math.floor(rect.height * dpr)
    }

    const tick = () => {
      const w = canvas.width
      const h = canvas.height
      if (w === 0 || h === 0) return

      if (reduced) {
        drawIdleBars(ctx, w, h, bars, idleColor)
        return
      }

      ensureSmoothed(smoothedRef, bars)
      const sm = smoothedRef.current!

      if (isPlaying) {
        const analyser = getAnalyser()
        if (!analyser) {
          decaySmoothedTowardIdle(sm, bars)
          drawBars(
            ctx,
            w,
            h,
            bars,
            sm,
            playColor,
            idleColor,
            true,
          )
          return
        }
        let buf = freqBufRef.current
        if (
          !buf ||
          buf.length !== analyser.frequencyBinCount
        ) {
          buf = new Uint8Array(
            new ArrayBuffer(analyser.frequencyBinCount),
          )
          freqBufRef.current = buf
        }
        analyser.getByteFrequencyData(buf)
        const step = Math.floor(buf.length / bars)
        const tickMs = performance.now()
        const tSec = tickMs * 0.001
        for (let i = 0; i < bars; i++) {
          let sum = 0
          for (let j = 0; j < step; j++) {
            sum += buf[i * step + j] || 0
          }
          const norm = sum / (step * 255)
          const shaped = shapeLevel(norm)
          const spread =
            (1 +
              BAR_SPREAD_AMP *
                Math.sin(i * 0.97 + tSec * 0.72)) *
            (1 +
              BAR_SPREAD_SLOW *
                Math.sin(i * 2.13 - tSec * 0.58))
          const jitter =
            DITHER_AMP * ditherUnit(i, tickMs)
          let raw = shaped * spread + jitter
          raw = Math.min(1, Math.max(MIN_PLAY_FRAC, raw))
          sm[i] += (raw - sm[i]) * ATTACK_SMOOTH
        }
        drawBars(
          ctx,
          w,
          h,
          bars,
          sm,
          playColor,
          idleColor,
          false,
        )
        return
      }

      decaySmoothedTowardIdle(sm, bars)
      drawBars(
        ctx,
        w,
        h,
        bars,
        sm,
        playColor,
        idleColor,
        true,
      )
    }

    resize()
    const ro = new ResizeObserver(() => {
      resize()
      tick()
    })
    ro.observe(canvas)

    tick()
    intervalRef.current = window.setInterval(
      tick,
      SPECTRUM_INTERVAL_MS,
    )

    return () => {
      ro.disconnect()
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [getAnalyser, isPlaying, bars, overlay])

  return (
    <canvas
      ref={canvasRef}
      className={`waveform${className ? ` ${className}` : ''}`}
      style={{
        width: '100%',
        height,
        display: 'block',
      }}
    />
  )
}
