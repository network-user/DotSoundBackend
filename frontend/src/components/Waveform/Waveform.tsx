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

const ATTACK = 0.45
const RELEASE = 0.10

const IDLE_AMP = 0.14

const VISUAL_CAP = 0.92
const NORM_GAIN = 1.16
const NORM_CURVE_EXP = 0.72

const EDGE_TAPER_POWER = 1.4

function easeOutQuad(x: number): number {
  return 1 - (1 - x) * (1 - x)
}

function shapeLevel(norm: number): number {
  const boosted = Math.min(1, norm * NORM_GAIN)
  const curved = boosted ** NORM_CURVE_EXP
  return curved * VISUAL_CAP
}

function edgeTaper(t: number): number {
  const u = t * 2 - 1
  const c = Math.cos(u * 1.05)
  return Math.max(0, c) ** EDGE_TAPER_POWER
}

function ensureLevels(
  ref: { current: Float32Array | null },
  n: number,
) {
  if (!ref.current || ref.current.length !== n) {
    ref.current = new Float32Array(n)
    ref.current.fill(IDLE_AMP)
  }
}

type LayerSpec = {
  scale: number
  fill: string
  glow: string
  glowBlur: number
}

function drawMirrorBand(
  ctx: CanvasRenderingContext2D,
  amps: Float32Array,
  w: number,
  cy: number,
  spec: LayerSpec,
  dpr: number,
) {
  const points = amps.length
  ctx.save()
  if (spec.glowBlur > 0) {
    ctx.shadowColor = spec.glow
    ctx.shadowBlur = spec.glowBlur * dpr
  }
  ctx.fillStyle = spec.fill
  ctx.beginPath()
  const stepX = w / (points - 1)
  ctx.moveTo(0, cy - amps[0] * spec.scale)
  for (let i = 0; i < points - 1; i++) {
    const x1 = i * stepX
    const y1 = cy - amps[i] * spec.scale
    const x2 = (i + 1) * stepX
    const y2 = cy - amps[i + 1] * spec.scale
    const mx = (x1 + x2) / 2
    const my = (y1 + y2) / 2
    ctx.quadraticCurveTo(x1, y1, mx, my)
  }
  ctx.lineTo(w, cy - amps[points - 1] * spec.scale)
  ctx.lineTo(w, cy + amps[points - 1] * spec.scale)
  for (let i = points - 1; i > 0; i--) {
    const x1 = i * stepX
    const y1 = cy + amps[i] * spec.scale
    const x2 = (i - 1) * stepX
    const y2 = cy + amps[i - 1] * spec.scale
    const mx = (x1 + x2) / 2
    const my = (y1 + y2) / 2
    ctx.quadraticCurveTo(x1, y1, mx, my)
  }
  ctx.lineTo(0, cy + amps[0] * spec.scale)
  ctx.closePath()
  ctx.fill()
  ctx.restore()
}

function drawCenterLine(
  ctx: CanvasRenderingContext2D,
  w: number,
  cy: number,
  color: string,
  dpr: number,
) {
  ctx.save()
  const stroke = Math.max(0.5, 0.6 * dpr)
  ctx.lineWidth = stroke
  ctx.strokeStyle = color
  ctx.beginPath()
  ctx.moveTo(0, cy)
  ctx.lineTo(w, cy)
  ctx.stroke()
  ctx.restore()
}

export function Waveform({
  height = 64,
  bars = 36,
  className,
  overlay = false,
  variant = 'default',
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const freqBufRef =
    useRef<Uint8Array<ArrayBuffer> | null>(null)
  const levelsRef = useRef<Float32Array | null>(null)
  const rafRef = useRef<number | null>(null)
  const lastTickRef = useRef<number>(0)
  const ampsRef = useRef<Float32Array | null>(null)
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

    const points = Math.max(16, Math.min(72, bars))
    ensureLevels(levelsRef, points)
    if (!ampsRef.current || ampsRef.current.length !== points) {
      ampsRef.current = new Float32Array(points)
    }
    const levels = levelsRef.current!
    const amps = ampsRef.current!

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

    const tonalC1 = overlay
      ? 'rgba(255,255,255,0.05)'
      : 'rgba(255,255,255,0.07)'
    const tonalC2 = overlay
      ? 'rgba(255,255,255,0.16)'
      : 'rgba(255,255,255,0.20)'
    const tonalC3 = overlay
      ? 'rgba(255,255,255,0.62)'
      : 'rgba(255,255,255,0.82)'
    const glowSoft = overlay
      ? 'rgba(255,255,255,0.35)'
      : 'rgba(255,255,255,0.48)'
    const centerLineColor = overlay
      ? 'rgba(255,255,255,0.07)'
      : 'rgba(255,255,255,0.10)'

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

      const halfH = h / 2
      const cy = halfH
      const tSec = now * 0.001

      const analyser = isPlaying ? getAnalyser() : null

      if (reduced) {
        for (let i = 0; i < points; i++) {
          levels[i] = IDLE_AMP
        }
      } else if (analyser) {
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
        const binCount = buf.length
        for (let i = 0; i < points; i++) {
          const t0 = i / points
          const t1 = (i + 1) / points
          const sN = Math.pow(t0, 1.7) * 0.85
          const eN = Math.pow(t1, 1.7) * 0.85 + 0.004
          const start = Math.floor(sN * binCount)
          const end = Math.min(
            binCount,
            Math.max(start + 1, Math.floor(eN * binCount)),
          )
          let sum = 0
          for (let j = start; j < end; j++) sum += buf[j]
          const norm = sum / ((end - start) * 255)
          const shaped = shapeLevel(norm)
          const target = Math.max(IDLE_AMP * 0.6, shaped)
          const cur = levels[i]
          const alpha = target > cur ? ATTACK : RELEASE
          levels[i] = cur + (target - cur) * alpha
        }
      } else {
        const breathe =
          (Math.sin(tSec * 0.85) + 1) * 0.5
        const amp =
          IDLE_AMP * (0.55 + 0.45 * easeOutQuad(breathe))
        for (let i = 0; i < points; i++) {
          const phase = tSec * 0.55 + i * 0.42
          const w0 = (Math.sin(phase) + 1) * 0.5
          const w1 =
            (Math.sin(phase * 1.7 + 1.2) + 1) * 0.5
          const target =
            amp * (0.5 + 0.35 * w0 + 0.15 * w1)
          levels[i] += (target - levels[i]) * 0.08
        }
      }

      for (let i = 0; i < points; i++) {
        const taper = edgeTaper(i / (points - 1))
        amps[i] = levels[i] * halfH * 0.94 * taper
      }

      drawCenterLine(ctx, w, cy, centerLineColor, dpr)
      const isRadio = variant === 'radio'
      const haloBlur = perfLite ? 10 : 22
      const midBlur = perfLite ? 4 : 8
      drawMirrorBand(
        ctx,
        amps,
        w,
        cy,
        {
          scale: isRadio ? 1.06 : 1.05,
          fill: tonalC1,
          glow: glowSoft,
          glowBlur: haloBlur,
        },
        dpr,
      )
      drawMirrorBand(
        ctx,
        amps,
        w,
        cy,
        {
          scale: isRadio ? 0.74 : 0.78,
          fill: tonalC2,
          glow: glowSoft,
          glowBlur: midBlur,
        },
        dpr,
      )
      drawMirrorBand(
        ctx,
        amps,
        w,
        cy,
        {
          scale: isRadio ? 0.38 : 0.42,
          fill: tonalC3,
          glow: 'rgba(0,0,0,0)',
          glowBlur: 0,
        },
        dpr,
      )
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
