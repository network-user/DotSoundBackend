import { useId, useMemo } from 'react'

export interface SparklinePoint {
  date: string
  value: number
}

interface Props {
  points: SparklinePoint[]
  width?: number
  height?: number
  ariaLabel?: string
}

/**
 * Lightweight SVG sparkline (no dependencies). Uses viewBox so the
 * caller controls actual rendered size via CSS. Renders the area
 * fill, the line stroke, and the last-point dot.
 */
export function Sparkline({
  points,
  width = 320,
  height = 56,
  ariaLabel,
}: Props) {
  const gradientId = useId().replace(/:/g, '')
  const path = useMemo(() => {
    if (points.length === 0) {
      return { line: '', area: '', last: null }
    }
    const max = Math.max(...points.map((p) => p.value), 1)
    const min = 0
    const padX = 2
    const padY = 4
    const span = points.length === 1 ? 1 : points.length - 1
    const xStep = (width - padX * 2) / span
    const yScale = (height - padY * 2) / Math.max(max - min, 1)
    const xy = points.map((p, i) => ({
      x: padX + i * xStep,
      y: height - padY - (p.value - min) * yScale,
    }))
    const line = xy
      .map((pt, i) =>
        i === 0 ? `M${pt.x},${pt.y}` : `L${pt.x},${pt.y}`,
      )
      .join(' ')
    const area =
      `M${xy[0].x},${height - padY} ` +
      xy.map((pt) => `L${pt.x},${pt.y}`).join(' ') +
      ` L${xy[xy.length - 1].x},${height - padY} Z`
    return { line, area, last: xy[xy.length - 1] }
  }, [points, width, height])

  if (points.length === 0) return null

  return (
    <svg
      className="rp-sparkline"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={ariaLabel}
    >
      <defs>
        <linearGradient
          id={`rp-sparkline-gradient-${gradientId}`}
          x1="0"
          y1="0"
          x2="0"
          y2="1"
        >
          <stop
            offset="0%"
            stopColor="currentColor"
            stopOpacity="0.35"
          />
          <stop
            offset="100%"
            stopColor="currentColor"
            stopOpacity="0"
          />
        </linearGradient>
      </defs>
      <path
        d={path.area}
        fill={`url(#rp-sparkline-gradient-${gradientId})`}
      />
      <path d={path.line} className="rp-sparkline__line" />
      {path.last && (
        <circle
          cx={path.last.x}
          cy={path.last.y}
          r={3.5}
          className="rp-sparkline__dot"
        />
      )}
    </svg>
  )
}
