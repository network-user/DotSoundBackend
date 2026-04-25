interface Props {
  data: number[]
  /** Playback progress 0–100 */
  progress: number
  onSeek: (pct: number) => void
  height?: number
  className?: string
}

/**
 * Static pre-computed waveform bar from stored waveform_data.
 * Bars left of the seek position use the accent colour; bars
 * to the right use the muted colour.
 */
export function WaveformBar({
  data,
  progress,
  onSeek,
  height = 48,
  className,
}: Props) {
  const total = data.length || 1

  const handleClick = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const pct = ((e.clientX - rect.left) / rect.width) * 100
    onSeek(Math.max(0, Math.min(100, pct)))
  }

  const handleTouch = (e: React.TouchEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const touch = e.changedTouches[0]
    const pct = ((touch.clientX - rect.left) / rect.width) * 100
    onSeek(Math.max(0, Math.min(100, pct)))
  }

  const barW = 0.55
  const gap = (1 - barW) / total
  const splitAt = (progress / 100) * total

  return (
    <svg
      viewBox={`0 0 ${total} 1`}
      preserveAspectRatio="none"
      height={height}
      style={{ width: '100%', display: 'block', cursor: 'pointer' }}
      className={`waveform-bar${className ? ` ${className}` : ''}`}
      onClick={handleClick}
      onTouchEnd={handleTouch}
      aria-label="Seek bar"
      role="slider"
      aria-valuenow={Math.round(progress)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {data.map((amp, i) => {
        const x = i + gap / 2
        const bh = Math.max(0.04, amp)
        const y = (1 - bh) / 2
        const played = i < splitAt
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={barW}
            height={bh}
            fill={played ? 'var(--clr-accent, #fff)' : 'var(--clr-waveform-idle, rgba(255,255,255,0.22))'}
          />
        )
      })}
    </svg>
  )
}
