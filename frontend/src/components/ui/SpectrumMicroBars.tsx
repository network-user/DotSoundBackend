import { useEffect, useRef } from 'react'
import { useReducedMotion } from '@/lib/motion'
import { isPerfLiteActive } from '@/lib/glassPerformance'

type Props = {
  active: boolean
  getAnalyser: () => AnalyserNode | null
  className?: string
}

const IDLE_PCT = 30

function bandAvg(
  buf: Uint8Array<ArrayBuffer>,
  start: number,
  end: number,
): number {
  if (end <= start) return 0
  let s = 0
  for (let i = start; i < end; i++) s += buf[i] ?? 0
  return s / ((end - start) * 255)
}

export function SpectrumMicroBars({
  active,
  getAnalyser,
  className,
}: Props) {
  const reduce = useReducedMotion()
  const r0 = useRef<HTMLSpanElement>(null)
  const r1 = useRef<HTMLSpanElement>(null)
  const r2 = useRef<HTMLSpanElement>(null)
  const refs = [r0, r1, r2] as const
  const bufRef = useRef<Uint8Array<ArrayBuffer> | null>(null)
  const lastPaintRef = useRef<number>(0)
  const smoothRef = useRef<[number, number, number]>([
    IDLE_PCT / 100,
    IDLE_PCT / 100,
    IDLE_PCT / 100,
  ])

  useEffect(() => {
    const setScales = (a: number, b: number, c: number) => {
      const xs = [a, b, c]
      for (let i = 0; i < 3; i++) {
        const el = refs[i].current
        if (el)
          el.style.transform = `scaleY(${Math.round(xs[i]! * 100) / 100})`
      }
    }

    if (!active || reduce) {
      smoothRef.current = [
        IDLE_PCT / 100,
        IDLE_PCT / 100,
        IDLE_PCT / 100,
      ]
      setScales(
        IDLE_PCT / 100,
        IDLE_PCT / 100,
        IDLE_PCT / 100,
      )
      return
    }

    let raf = 0
    let stopped = false
    const attack = 0.42
    const decay = 0.22
    const frameMs = isPerfLiteActive() ? 50 : 1000 / 30

    const tick = (now: number) => {
      if (stopped) return
      if (now - lastPaintRef.current < frameMs) {
        raf = requestAnimationFrame(tick)
        return
      }
      lastPaintRef.current = now
      const a = getAnalyser()
      let targets: [number, number, number] = [
        IDLE_PCT / 100,
        IDLE_PCT / 100,
        IDLE_PCT / 100,
      ]
      if (a) {
        let buf = bufRef.current
        if (!buf || buf.length !== a.frequencyBinCount) {
          buf = new Uint8Array(
            new ArrayBuffer(a.frequencyBinCount),
          )
          bufRef.current = buf
        }
        a.getByteFrequencyData(buf)
        const n = buf.length
        const loEnd = Math.max(2, Math.floor(n * 0.12))
        const midEnd = Math.max(
          loEnd + 1,
          Math.floor(n * 0.42),
        )
        const low = bandAvg(buf, 0, loEnd)
        const mid = bandAvg(buf, loEnd, midEnd)
        const high = bandAvg(buf, midEnd, n)
        targets = [
          0.2 + low * 0.82,
          0.2 + mid * 0.82,
          0.2 + high * 0.82,
        ]
      }
      const sm = smoothRef.current
      for (let i = 0; i < 3; i++) {
        const t = targets[i]!
        const prev = sm[i]!
        const alpha = t > prev ? attack : decay
        sm[i] = prev + (t - prev) * alpha
      }
      setScales(sm[0]!, sm[1]!, sm[2]!)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => {
      stopped = true
      cancelAnimationFrame(raf)
    }
  }, [active, getAnalyser, reduce])

  return (
    <span
      className={[
        'player-radio-pill__waves',
        'player-radio-pill__waves--spectrum',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      aria-hidden
    >
      <span ref={r0} />
      <span ref={r1} />
      <span ref={r2} />
    </span>
  )
}
