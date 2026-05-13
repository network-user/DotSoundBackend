import {
  useEffect,
  useRef,
} from 'react'
import {
  usePlayerActions,
  usePlayerPlayback,
} from '@/store/PlayerContext'

interface Props {
  height?: number
  bars?: number
  className?: string
  overlay?: boolean
  variant?: 'default' | 'radio'
}

const REDUCED_MOTION_QUERY =
  '(prefers-reduced-motion: reduce)'

const FRAME_INTERVAL_MS = 1000 / 60
const FRAME_INTERVAL_LITE_MS = 1000 / 30

const MAX_CANVAS_DPR = 1.5

const ATTACK = 0.55
const RELEASE = 0.18

const IDLE_AMP = 0.06

const EDGE_TAPER_POWER = 1.5

function easeOutQuad(x: number): number {
  return 1 - (1 - x) * (1 - x)
}

function edgeTaper(t: number): number {
  const u = t * 2 - 1
  const c = Math.cos(u * 1.05)
  return Math.max(0, c) ** EDGE_TAPER_POWER
}

function ensureSamples(
  ref: { current: Float32Array | null },
  n: number,
) {
  if (!ref.current || ref.current.length !== n) {
    ref.current = new Float32Array(n)
    ref.current.fill(0)
  }
}

export function Waveform({
  height = 64,
  bars = 64,
  className,
  overlay = false,
  variant = 'default',
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const timeBufRef =
    useRef<Uint8Array<ArrayBuffer> | null>(null)
  const samplesRef = useRef<Float32Array | null>(null)
  const rafRef = useRef<number | null>(null)
  const lastTickRef = useRef<number>(0)
  const { isPlaying } = usePlayerPlayback()
  const { getAnalyser } = usePlayerActions()

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const reduced = window.matchMedia(
      REDUCED_MOTION_QUERY,
    ).matches
    const perfLite =
      typeof document !== 'undefined' &&
      document.body.classList.contains('ds-perf-lite')

    const points = Math.max(48, Math.min(160, bars * 2))
    ensureSamples(samplesRef, points)
    const samples = samplesRef.current!

    const interval =
      perfLite || reduced
        ? FRAME_INTERVAL_LITE_MS
        : FRAME_INTERVAL_MS

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      const dpr = Math.min(
        window.devicePixelRatio || 1,
        MAX_CANVAS_DPR,
      )
      canvas.width = Math.floor(rect.width * dpr)
      canvas.height = Math.floor(rect.height * dpr)
    }

    const lineColor = overlay
      ? 'rgba(255,255,255,0.88)'
      : 'rgba(255,255,255,0.96)'
    const glowColor = overlay
      ? 'rgba(255,255,255,0.38)'
      : 'rgba(255,255,255,0.55)'
    const centerLineColor = overlay
      ? 'rgba(255,255,255,0.06)'
      : 'rgba(255,255,255,0.09)'

    const render = (now: number) => {
      rafRef.current = requestAnimationFrame(render)
      if (now - lastTickRef.current < interval) return
      lastTickRef.current = now

      const w = canvas.width
      const h = canvas.height
      if (w === 0 || h === 0) return

      const dpr = Math.min(
        window.devicePixelRatio || 1,
        MAX_CANVAS_DPR,
      )
      ctx.clearRect(0, 0, w, h)

      const cy = h / 2
      const halfH = h / 2
      const tSec = now * 0.001

      const analyser = isPlaying ? getAnalyser() : null

      if (reduced) {
        for (let i = 0; i < points; i++) samples[i] = 0
      } else if (analyser) {
        let buf = timeBufRef.current
        const fftSize = analyser.fftSize
        if (!buf || buf.length !== fftSize) {
          buf = new Uint8Array(new ArrayBuffer(fftSize))
          timeBufRef.current = buf
        }
        analyser.getByteTimeDomainData(buf)
        const binCount = buf.length
        const step = binCount / points
        for (let i = 0; i < points; i++) {
          const start = Math.floor(i * step)
          const end = Math.min(
            binCount,
            Math.max(start + 1, Math.floor((i + 1) * step)),
          )
          let sum = 0
          for (let j = start; j < end; j++) {
            // 128 == silence midpoint; map to -1..1
            sum += (buf[j] - 128) / 128
          }
          const target = sum / (end - start)
          const cur = samples[i]
          const alpha = Math.abs(target) > Math.abs(cur) ? ATTACK : RELEASE
          samples[i] = cur + (target - cur) * alpha
        }
      } else {
        const breathe =
          (Math.sin(tSec * 0.85) + 1) * 0.5
        const amp =
          IDLE_AMP * (0.6 + 0.4 * easeOutQuad(breathe))
        for (let i = 0; i < points; i++) {
          const t = i / (points - 1)
          const phase = tSec * 0.95 + t * 6.2
          const w0 = Math.sin(phase)
          const w1 = Math.sin(phase * 1.7 + 1.2) * 0.5
          const target = amp * (w0 + w1)
          samples[i] += (target - samples[i]) * 0.12
        }
      }

      // Subtle center line as anchor
      ctx.save()
      const stroke0 = Math.max(0.5, 0.6 * dpr)
      ctx.lineWidth = stroke0
      ctx.strokeStyle = centerLineColor
      ctx.beginPath()
      ctx.moveTo(0, cy)
      ctx.lineTo(w, cy)
      ctx.stroke()
      ctx.restore()

      const isRadio = variant === 'radio'
      const ampScale = halfH * (isRadio ? 0.78 : 0.72)
      const stepX = w / (points - 1)

      const yAt = (i: number) => {
        const t = i / (points - 1)
        return cy - samples[i] * ampScale * edgeTaper(t)
      }

      // Build a smooth quadratic path
      const drawPath = () => {
        ctx.beginPath()
        ctx.moveTo(0, yAt(0))
        for (let i = 0; i < points - 1; i++) {
          const x1 = i * stepX
          const y1 = yAt(i)
          const x2 = (i + 1) * stepX
          const y2 = yAt(i + 1)
          const mx = (x1 + x2) / 2
          const my = (y1 + y2) / 2
          ctx.quadraticCurveTo(x1, y1, mx, my)
        }
        ctx.lineTo(w, yAt(points - 1))
      }

      // Glow underlay
      if (!perfLite) {
        ctx.save()
        ctx.shadowColor = glowColor
        ctx.shadowBlur = (isRadio ? 14 : 10) * dpr
        ctx.lineWidth = Math.max(1, 1.6 * dpr)
        ctx.strokeStyle = lineColor
        ctx.lineCap = 'round'
        ctx.lineJoin = 'round'
        drawPath()
        ctx.stroke()
        ctx.restore()
      }

      // Crisp top line
      ctx.save()
      ctx.lineWidth = Math.max(0.75, 1.25 * dpr)
      ctx.strokeStyle = lineColor
      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'
      drawPath()
      ctx.stroke()
      ctx.restore()
    }

    resize()
    const ro = new ResizeObserver(() => {
      resize()
    })
    ro.observe(canvas)

    rafRef.current = requestAnimationFrame(render)

    return () => {
      ro.disconnect()
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }
  }, [getAnalyser, isPlaying, bars, overlay, variant])

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
