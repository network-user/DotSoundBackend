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

const MIN_PLAY_FRAC = 0.05

const ATTACK_SMOOTH = 0.48

const DECAY_SMOOTH = 0.2

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
  const barW = (w / bars) * 0.6
  const gap = (w / bars) * 0.4
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
  const barW = (w / bars) * 0.6
  const gap = (w / bars) * 0.4
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
      ? 'rgba(255,255,255,0.5)'
      : 'rgba(255,255,255,0.85)'

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
          for (let i = 0; i < bars; i++) {
            sm[i] +=
              (IDLE_FRAC - sm[i]) * DECAY_SMOOTH
          }
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
        for (let i = 0; i < bars; i++) {
          let sum = 0
          for (let j = 0; j < step; j++) {
            sum += buf[i * step + j] || 0
          }
          const norm = sum / (step * 255)
          const target = Math.max(
            MIN_PLAY_FRAC,
            norm,
          )
          sm[i] += (target - sm[i]) * ATTACK_SMOOTH
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

      for (let i = 0; i < bars; i++) {
        sm[i] +=
          (IDLE_FRAC - sm[i]) * DECAY_SMOOTH
      }
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
