import {
  memo,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type RefObject,
} from 'react'
import { m, SPRING_SNAPPY } from '@/lib/motion'

interface SeekProps {
  duration: number
  trackId: number | string
  isPlaying: boolean
  getPreciseTime: () => number
  onSeek: (pct: number) => void
  parentRef: RefObject<HTMLElement | null>
}

interface TimeProps {
  duration: number
  trackId: number | string
  isPlaying: boolean
  getPreciseTime: () => number
}

const LABEL_INTERVAL_MS = 250
const SEEK_FRAME_MS = 33

function fmt(sec: number) {
  if (!sec || isNaN(sec)) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
    .toString()
    .padStart(2, '0')
  return `${m}:${s}`
}

function clampPct(value: number): number {
  if (!Number.isFinite(value)) return 0
  if (value < 0) return 0
  if (value > 100) return 100
  return Number(value.toFixed(3))
}

function PlayerBarSeekInner({
  duration,
  trackId,
  isPlaying,
  getPreciseTime,
  onSeek,
  parentRef,
}: SeekProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const draggingRef = useRef(false)

  const writePct = (pct: number) => {
    const clamped = clampPct(pct)
    if (parentRef.current) {
      parentRef.current.style.setProperty(
        '--progress',
        `${clamped}%`,
      )
    }
    if (inputRef.current && !draggingRef.current) {
      inputRef.current.value = String(clamped)
    }
  }

  useEffect(() => {
    const now = getPreciseTime()
    writePct(duration ? (now / duration) * 100 : 0)
    if (!isPlaying) return
    let rafId = 0
    let lastFrameTime = 0
    const frame = (ts: number) => {
      if (ts - lastFrameTime >= SEEK_FRAME_MS) {
        lastFrameTime = ts
        const t = getPreciseTime()
        writePct(duration ? (t / duration) * 100 : 0)
      }
      rafId = window.requestAnimationFrame(frame)
    }
    rafId = window.requestAnimationFrame(frame)
    return () => {
      window.cancelAnimationFrame(rafId)
    }
  }, [isPlaying, trackId, duration, getPreciseTime])

  const seekStyle = {
    '--progress': 'var(--progress, 0%)',
  } as CSSProperties

  return (
    <div
      id="pb-seek-wrap"
      className="pb-seek-zone rp-player-seek"
    >
      <m.input
        ref={inputRef}
        type="range"
        id="pb-seek"
        min={0}
        max={100}
        step={0.1}
        defaultValue={0}
        style={seekStyle}
        aria-label="Перемотка трека"
        onPointerDown={() => {
          draggingRef.current = true
        }}
        onPointerUp={() => {
          draggingRef.current = false
        }}
        onPointerCancel={() => {
          draggingRef.current = false
        }}
        onChange={(e) =>
          onSeek(Number(e.currentTarget.value))
        }
        transition={SPRING_SNAPPY}
      />
    </div>
  )
}

function PlayerBarTimeInner({
  duration,
  trackId,
  isPlaying,
  getPreciseTime,
}: TimeProps) {
  const [labelTime, setLabelTime] = useState(() =>
    getPreciseTime(),
  )

  useEffect(() => {
    setLabelTime(getPreciseTime())
    if (!isPlaying) return
    const id = window.setInterval(() => {
      setLabelTime(getPreciseTime())
    }, LABEL_INTERVAL_MS)
    return () => {
      window.clearInterval(id)
    }
  }, [isPlaying, trackId, getPreciseTime])

  return (
    <div id="pb-time">
      <span>{fmt(labelTime)}</span>
      <span>{fmt(duration)}</span>
    </div>
  )
}

export const PlayerBarSeek = memo(PlayerBarSeekInner)
export const PlayerBarTime = memo(PlayerBarTimeInner)
