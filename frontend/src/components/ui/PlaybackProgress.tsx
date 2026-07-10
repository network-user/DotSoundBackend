import {
  memo,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type CSSProperties,
} from 'react'
import { usePlayerTime } from '@/store/PlayerContext'
import { isPerfLiteActive } from '@/lib/glassPerformance'
import { WaveformBar } from '@/components/Waveform/WaveformBar'

// ---------------------------------------------------------------------------
// Shared playback-progress leaves.
//
// The heavy overlays (TrackCardSheet, NowPlayingView, FullscreenLyrics,
// LyricsPanel) used to subscribe to ``usePlayerState()`` — which carries
// ``currentTime`` and therefore re-rendered the entire overlay ~25 times a
// second. These leaves move all ``currentTime`` consumption out of the heavy
// parents and into tiny memoized components, mirroring the shipped
// ``PlayerBar/PlayerBarProgress`` pattern:
//
//   * the seek bar position is driven at frame rate via a rAF loop that
//     writes the ``--progress`` CSS variable / fill width / uncontrolled
//     ``input.value`` straight to the DOM — zero React re-renders per frame;
//   * the rAF loop is gated on ``isPlaying`` and, because browsers do not
//     fire ``requestAnimationFrame`` for hidden documents, it also stops on
//     ``document.hidden`` on its own (same as the reference — no extra
//     visibilitychange listener needed);
//   * discrete / paused updates (seek while paused, metadata arriving late)
//     are reflected via ``PausedTimeSync``, a null-rendering leaf that is
//     mounted only while paused so it subscribes to ``usePlayerTime`` only
//     when it actually has to.
//
// Parents pass ``isPlaying`` / ``duration`` from ``usePlayerPlayback()`` and
// never touch ``currentTime`` themselves.
// ---------------------------------------------------------------------------

function fmt(sec: number): string {
  if (!sec || Number.isNaN(sec)) return '0:00'
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
  return value
}

/**
 * Null-rendering leaf that subscribes to ``usePlayerTime`` and forwards the
 * current time (in seconds) to ``onTick``. Mount it only while paused: while
 * playing the rAF loops own the DOM, and keeping this unmounted means the
 * currentTime subscription (and its re-renders) exist only when paused, where
 * ``currentTime`` changes at most once per seek.
 */
function PausedTimeSyncInner({
  onTick,
}: {
  onTick: (seconds: number) => void
}) {
  const { currentTime } = usePlayerTime()
  useEffect(() => {
    onTick(currentTime)
  }, [currentTime, onTick])
  return null
}
export const PausedTimeSync = memo(PausedTimeSyncInner)

interface PlaybackSeekProps {
  trackId: number | string
  duration: number
  isPlaying: boolean
  getPreciseTime: () => number
  onSeek: (pct: number) => void
  inputClassName: string
  ariaLabel: string
  /** Optional wrapper element rendered around fill + input. */
  wrapClassName?: string
  /** When set, a fill element is rendered and its width is driven. */
  fillClassName?: string
  /** When true, the ``--progress`` CSS variable is written on the input. */
  writeProgressVar?: boolean
  step?: number
}

/**
 * Uncontrolled range seek bar. Writes ``--progress`` / fill width /
 * ``input.value`` imperatively via rAF while playing and via ``PausedTimeSync``
 * while paused; ``onChange`` keeps the fill glued to the thumb during a drag.
 */
function PlaybackSeekInner({
  trackId,
  duration,
  isPlaying,
  getPreciseTime,
  onSeek,
  inputClassName,
  ariaLabel,
  wrapClassName,
  fillClassName,
  writeProgressVar = false,
  step = 0.1,
}: PlaybackSeekProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const fillRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)

  // Seed the first paint from live audio time so the bar/thumb do not flash
  // at 0% before the first effect runs.
  const [initialPct] = useState<number>(() =>
    clampPct(duration ? (getPreciseTime() / duration) * 100 : 0),
  )
  // Holds the last written percentage so the rare re-renders of this leaf
  // (play/pause, track change) re-seed fill/``--progress`` from the latest
  // value instead of flashing back to the first-mount position.
  const lastPctRef = useRef<number>(initialPct)

  const applyPct = useCallback(
    (pct: number) => {
      const c = clampPct(pct)
      lastPctRef.current = c
      const input = inputRef.current
      if (fillRef.current) {
        fillRef.current.style.width = `${c}%`
      }
      if (writeProgressVar && input) {
        input.style.setProperty('--progress', `${c}%`)
      }
      if (input && !draggingRef.current) {
        input.value = String(c)
      }
    },
    [writeProgressVar],
  )

  // Frame-rate updates while playing (rAF auto-pauses on document.hidden).
  useEffect(() => {
    if (!isPlaying) return
    applyPct(duration ? (getPreciseTime() / duration) * 100 : 0)
    let rafId = 0
    let last = 0
    const frameMs = isPerfLiteActive() ? 1000 / 30 : 1000 / 60
    const frame = (now: number) => {
      if (!draggingRef.current && now - last >= frameMs) {
        last = now
        applyPct(duration ? (getPreciseTime() / duration) * 100 : 0)
      }
      rafId = requestAnimationFrame(frame)
    }
    rafId = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(rafId)
  }, [isPlaying, trackId, duration, getPreciseTime, applyPct])

  const pausedTick = useCallback(
    (sec: number) => {
      if (draggingRef.current) return
      applyPct(duration ? (sec / duration) * 100 : 0)
    },
    [duration, applyPct],
  )

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const v = Number(e.currentTarget.value)
    applyPct(v)
    onSeek(v)
  }
  const startDrag = () => {
    draggingRef.current = true
  }
  const endDrag = () => {
    draggingRef.current = false
  }

  const inner = (
    <>
      {fillClassName ? (
        <div
          className={fillClassName}
          ref={fillRef}
          style={{ width: `${lastPctRef.current}%` }}
        />
      ) : null}
      <input
        ref={inputRef}
        type="range"
        className={inputClassName}
        min={0}
        max={100}
        step={step}
        defaultValue={initialPct}
        aria-label={ariaLabel}
        style={
          writeProgressVar
            ? ({
                ['--progress']: `${lastPctRef.current}%`,
              } as CSSProperties)
            : undefined
        }
        onChange={handleChange}
        onPointerDown={startDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      />
      {!isPlaying ? <PausedTimeSync onTick={pausedTick} /> : null}
    </>
  )

  return wrapClassName ? (
    <div className={wrapClassName}>{inner}</div>
  ) : (
    inner
  )
}
export const PlaybackSeek = memo(PlaybackSeekInner)

interface PlaybackWaveformProps {
  trackId: number | string
  duration: number
  isPlaying: boolean
  getPreciseTime: () => number
  onSeek: (pct: number) => void
  data: number[]
  height?: number
  className?: string
  durationSec?: number
}

/**
 * WaveformBar seek that owns its own progress state so the frame-rate updates
 * re-render only this leaf (and the SVG) rather than the whole card.
 */
function PlaybackWaveformInner({
  trackId,
  duration,
  isPlaying,
  getPreciseTime,
  onSeek,
  data,
  height,
  className,
  durationSec,
}: PlaybackWaveformProps) {
  const [progress, setProgress] = useState(() =>
    clampPct(duration ? (getPreciseTime() / duration) * 100 : 0),
  )

  useEffect(() => {
    if (!isPlaying) return
    setProgress(clampPct(duration ? (getPreciseTime() / duration) * 100 : 0))
    let rafId = 0
    let last = 0
    const frameMs = isPerfLiteActive() ? 1000 / 30 : 1000 / 60
    const frame = (now: number) => {
      if (now - last >= frameMs) {
        last = now
        setProgress(
          clampPct(duration ? (getPreciseTime() / duration) * 100 : 0),
        )
      }
      rafId = requestAnimationFrame(frame)
    }
    rafId = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(rafId)
  }, [isPlaying, trackId, duration, getPreciseTime])

  const pausedTick = useCallback(
    (sec: number) => {
      setProgress(clampPct(duration ? (sec / duration) * 100 : 0))
    },
    [duration],
  )

  const handleSeek = useCallback(
    (pct: number) => {
      setProgress(clampPct(pct))
      onSeek(pct)
    },
    [onSeek],
  )

  return (
    <>
      <WaveformBar
        data={data}
        progress={progress}
        onSeek={handleSeek}
        height={height}
        className={className}
        durationSec={durationSec}
      />
      {!isPlaying ? <PausedTimeSync onTick={pausedTick} /> : null}
    </>
  )
}
export const PlaybackWaveform = memo(PlaybackWaveformInner)

/**
 * Current-time label. Subscribes to ``usePlayerTime`` so only this span
 * re-renders as the clock advances; the parent stays off ``currentTime``.
 */
function PlaybackTimeInner({ className }: { className?: string }) {
  const { currentTime } = usePlayerTime()
  return <span className={className}>{fmt(currentTime)}</span>
}
export const PlaybackTime = memo(PlaybackTimeInner)

interface PlaybackLeadInProps {
  firstLineTimeMs: number
  offsetMs?: number
  thresholdMs?: number
  onSeek: () => void
  wrapClassName: string
  labelClassName: string
  timeClassName: string
  label: string
}

/**
 * "Starts in X.X" lyrics countdown shown before the first synced line. Isolated
 * so the per-tick countdown re-renders only this button, not the lyrics list.
 * Mount it only while it is relevant (before the first active line).
 */
function PlaybackLeadInInner({
  firstLineTimeMs,
  offsetMs = 0,
  thresholdMs = 250,
  onSeek,
  wrapClassName,
  labelClassName,
  timeClassName,
  label,
}: PlaybackLeadInProps) {
  const { currentTime } = usePlayerTime()
  const leadInMs = Math.max(
    0,
    firstLineTimeMs - (currentTime * 1000 + offsetMs),
  )
  if (leadInMs <= thresholdMs) return null
  return (
    <button type="button" className={wrapClassName} onClick={onSeek}>
      <span className={labelClassName}>{label}</span>
      <span className={timeClassName}>{(leadInMs / 1000).toFixed(1)}</span>
    </button>
  )
}
export const PlaybackLeadIn = memo(PlaybackLeadInInner)
