import { useEffect, useRef } from 'react'
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

/** Decorative spectrum only; low rate limits GPU wakeups vs RAF @ display Hz. */
const SPECTRUM_INTERVAL_MS = Math.round(1000 / 12)

const MAX_CANVAS_DPR = 1.25

/**
 * Realtime audio spectrum bars driven by the shared
 * AnalyserNode in PlayerContext. Canvas render only while
 * `isPlaying` at a low fixed rate; idle bars when paused.
 * Respects prefers-reduced-motion.
 */
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

    const drawIdle = () => {
      const w = canvas.width
      const h = canvas.height
      ctx.clearRect(0, 0, w, h)
      ctx.fillStyle = idleColor
      const barW = (w / bars) * 0.6
      const gap = (w / bars) * 0.4
      for (let i = 0; i < bars; i++) {
        const x = i * (barW + gap) + gap / 2
        const bh = h * 0.18
        const y = (h - bh) / 2
        ctx.fillRect(x, y, barW, bh)
      }
    }

    const drawSpectrum = () => {
      const analyser = getAnalyser()
      const w = canvas.width
      const h = canvas.height
      if (!analyser || !isPlaying) {
        drawIdle()
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
      ctx.clearRect(0, 0, w, h)
      analyser.getByteFrequencyData(buf)
      const barW = (w / bars) * 0.6
      const gap = (w / bars) * 0.4
      const step = Math.floor(buf.length / bars)
      ctx.fillStyle = playColor
      for (let i = 0; i < bars; i++) {
        let sum = 0
        for (let j = 0; j < step; j++) {
          sum += buf[i * step + j] || 0
        }
        const norm = sum / (step * 255)
        const bh = Math.max(h * 0.05, norm * h)
        const x = i * (barW + gap) + gap / 2
        const y = (h - bh) / 2
        ctx.fillRect(x, y, barW, bh)
      }
    }

    resize()
    const ro = new ResizeObserver(() => {
      resize()
      if (reduced || !isPlaying) {
        drawIdle()
      } else {
        drawSpectrum()
      }
    })
    ro.observe(canvas)

    if (reduced) {
      drawIdle()
    } else if (isPlaying) {
      drawSpectrum()
      intervalRef.current = window.setInterval(
        drawSpectrum,
        SPECTRUM_INTERVAL_MS,
      )
    } else {
      drawIdle()
    }

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
