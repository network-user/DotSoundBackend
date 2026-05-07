import {
  useEffect,
  useId,
  useRef,
  useState,
} from 'react'

interface Props {
  data: number[]
  /** Playback progress 0–100 */
  progress: number
  onSeek: (pct: number) => void
  height?: number
  className?: string
  /** Optional total track duration in seconds; enables time tooltip */
  durationSec?: number
}

function _fmt(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

export function WaveformBar({
  data,
  progress,
  onSeek,
  height = 48,
  className,
  durationSec,
}: Props) {
  const clipId = useId()
  const total = data.length || 1
  const svgRef = useRef<SVGSVGElement | null>(null)
  const draggingRef = useRef(false)
  const lastPctRef = useRef<number | null>(null)
  const [hoverPct, setHoverPct] = useState<number | null>(null)
  const [showTip, setShowTip] = useState(false)

  const _pctFromClient = (clientX: number) => {
    const el = svgRef.current
    if (!el) return null
    const rect = el.getBoundingClientRect()
    if (rect.width <= 0) return null
    const raw = ((clientX - rect.left) / rect.width) * 100
    return Math.max(0, Math.min(100, raw))
  }

  const _commitSeek = (clientX: number) => {
    const pct = _pctFromClient(clientX)
    if (pct == null) return
    lastPctRef.current = pct
    onSeek(pct)
  }

  useEffect(() => {
    const onMove = (ev: MouseEvent) => {
      if (!draggingRef.current) return
      const pct = _pctFromClient(ev.clientX)
      if (pct == null) return
      lastPctRef.current = pct
      setHoverPct(pct)
      onSeek(pct)
    }
    const onUp = () => {
      if (!draggingRef.current) return
      draggingRef.current = false
      setShowTip(false)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [onSeek])

  useEffect(() => {
    const onMove = (ev: TouchEvent) => {
      if (!draggingRef.current) return
      const t = ev.touches[0]
      if (!t) return
      const pct = _pctFromClient(t.clientX)
      if (pct == null) return
      lastPctRef.current = pct
      setHoverPct(pct)
      onSeek(pct)
      ev.preventDefault()
    }
    const onEnd = () => {
      if (!draggingRef.current) return
      draggingRef.current = false
      setShowTip(false)
    }
    window.addEventListener('touchmove', onMove, { passive: false })
    window.addEventListener('touchend', onEnd)
    window.addEventListener('touchcancel', onEnd)
    return () => {
      window.removeEventListener('touchmove', onMove)
      window.removeEventListener('touchend', onEnd)
      window.removeEventListener('touchcancel', onEnd)
    }
  }, [onSeek])

  const handleMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
    draggingRef.current = true
    setShowTip(true)
    _commitSeek(e.clientX)
    setHoverPct(_pctFromClient(e.clientX))
  }

  const handleMouseMoveHover = (e: React.MouseEvent<SVGSVGElement>) => {
    if (draggingRef.current) return
    setHoverPct(_pctFromClient(e.clientX))
  }

  const handleMouseEnter = () => setShowTip(true)
  const handleMouseLeave = () => {
    if (!draggingRef.current) setShowTip(false)
    setHoverPct(null)
  }

  const handleTouchStart = (e: React.TouchEvent<SVGSVGElement>) => {
    const t = e.touches[0]
    if (!t) return
    draggingRef.current = true
    setShowTip(true)
    _commitSeek(t.clientX)
    setHoverPct(_pctFromClient(t.clientX))
  }

  const handleKeyDown = (e: React.KeyboardEvent<SVGSVGElement>) => {
    if (e.key === 'ArrowLeft') {
      e.preventDefault()
      onSeek(Math.max(0, progress - 5))
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      onSeek(Math.min(100, progress + 5))
    } else if (e.key === 'Home') {
      e.preventDefault()
      onSeek(0)
    } else if (e.key === 'End') {
      e.preventDefault()
      onSeek(100)
    }
  }

  const barW = 0.55
  const gap = (1 - barW) / total
  const clampedProgress = Math.max(0, Math.min(100, progress))
  const playedUnits = (clampedProgress / 100) * total

  const tipPct = hoverPct ?? progress
  const tipSec = durationSec ? (tipPct / 100) * durationSec : null

  return (
    <div
      className={`waveform-bar-wrap${className ? ` ${className}-wrap` : ''}`}
      style={{ position: 'relative', width: '100%' }}
    >
      <svg
        ref={svgRef}
        viewBox={`0 0 ${total} 1`}
        preserveAspectRatio="none"
        height={height}
        style={{
          width: '100%',
          display: 'block',
          cursor: 'pointer',
          touchAction: 'none',
        }}
        className={`waveform-bar${className ? ` ${className}` : ''}`}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMoveHover}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onTouchStart={handleTouchStart}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        aria-label="Seek bar"
        role="slider"
        aria-valuenow={Math.round(clampedProgress)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={tipSec != null ? _fmt(tipSec) : undefined}
      >
        <defs>
          <clipPath id={clipId}>
            <rect
              x={0}
              y={0}
              width={playedUnits}
              height={1}
            />
          </clipPath>
        </defs>
        <rect
          x={0}
          y={0}
          width={total}
          height={1}
          fill="var(--clr-waveform-glass-idle, rgba(255,255,255,0.04))"
        />
        <rect
          x={0}
          y={0}
          width={playedUnits}
          height={1}
          fill="var(--clr-waveform-glass-played, rgba(255,255,255,0.18))"
        />
        {data.map((amp, i) => {
          const x = i + gap / 2
          const bh = Math.max(0.04, amp)
          const y = (1 - bh) / 2
          return (
            <rect
              key={`idle-${i}`}
              x={x}
              y={y}
              width={barW}
              height={bh}
              fill="var(--clr-waveform-idle, rgba(255,255,255,0.22))"
            />
          )
        })}
        <g clipPath={`url(#${clipId})`}>
          {data.map((amp, i) => {
            const x = i + gap / 2
            const bh = Math.max(0.04, amp)
            const y = (1 - bh) / 2
            return (
              <rect
                key={`played-${i}`}
                x={x}
                y={y}
                width={barW}
                height={bh}
                fill="var(--clr-accent, #fff)"
              />
            )
          })}
        </g>
      </svg>
      {showTip && hoverPct != null && tipSec != null && (
        <div
          className="waveform-bar-tip"
          style={{
            position: 'absolute',
            left: `${hoverPct}%`,
            transform: 'translate(-50%, -100%)',
            top: -4,
            pointerEvents: 'none',
            background: 'var(--clr-surface-elevated, rgba(20,20,20,0.92))',
            color: 'var(--clr-text, #fff)',
            font: '11px/1 ui-sans-serif, system-ui',
            padding: '3px 6px',
            borderRadius: 6,
            whiteSpace: 'nowrap',
            boxShadow: '0 2px 8px rgba(0,0,0,0.25)',
          }}
        >
          {_fmt(tipSec)}
        </div>
      )}
    </div>
  )
}
