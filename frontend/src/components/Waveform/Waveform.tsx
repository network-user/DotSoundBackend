import { useEffect, useRef } from 'react'
import { usePlayerActions, usePlayerState } from '@/store/PlayerContext'

interface Props {
  height?: number
  bars?: number
  className?: string
}

const REDUCED_MOTION_QUERY =
  '(prefers-reduced-motion: reduce)'

/**
 * Realtime audio spectrum bars driven by the shared
 * AnalyserNode in PlayerContext. Cheap canvas render,
 * pauses when audio is not playing and respects
 * prefers-reduced-motion.
 */
export function Waveform({
  height = 64,
  bars = 56,
  className,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number | null>(null)
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

    const dpr = window.devicePixelRatio || 1
    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      canvas.width = Math.floor(rect.width * dpr)
      canvas.height = Math.floor(rect.height * dpr)
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)

    const drawIdle = () => {
      const w = canvas.width
      const h = canvas.height
      ctx.clearRect(0, 0, w, h)
      ctx.fillStyle = 'rgba(255,255,255,0.15)'
      const barW = (w / bars) * 0.6
      const gap = (w / bars) * 0.4
      for (let i = 0; i < bars; i++) {
        const x = i * (barW + gap) + gap / 2
        const bh = h * 0.18
        const y = (h - bh) / 2
        ctx.fillRect(x, y, barW, bh)
      }
    }

    const draw = () => {
      const analyser = getAnalyser()
      const w = canvas.width
      const h = canvas.height
      ctx.clearRect(0, 0, w, h)
      if (!analyser || !isPlaying) {
        drawIdle()
        return
      }
      const data = new Uint8Array(
        analyser.frequencyBinCount,
      )
      analyser.getByteFrequencyData(data)
      const barW = (w / bars) * 0.6
      const gap = (w / bars) * 0.4
      const step = Math.floor(data.length / bars)
      ctx.fillStyle = 'rgba(255,255,255,0.85)'
      for (let i = 0; i < bars; i++) {
        let sum = 0
        for (let j = 0; j < step; j++) {
          sum += data[i * step + j] || 0
        }
        const norm = sum / (step * 255)
        const bh = Math.max(h * 0.05, norm * h)
        const x = i * (barW + gap) + gap / 2
        const y = (h - bh) / 2
        ctx.fillRect(x, y, barW, bh)
      }
    }

    const tick = () => {
      draw()
      rafRef.current = window.requestAnimationFrame(tick)
    }

    if (reduced) {
      drawIdle()
    } else {
      rafRef.current = window.requestAnimationFrame(tick)
    }

    return () => {
      ro.disconnect()
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }
  }, [getAnalyser, isPlaying, bars])

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
