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
  const uid = useId().replace(/:/g, '')
  const gradientId = `rp-sparkline-gradient-${uid}`
  const glowId = `rp-sparkline-glow-${uid}`

  const path = useMemo(() => {
    if (points.length === 0) {
      return { line: '', area: '', last: null }
    }
    const max = Math.max(...points.map((p) => p.value), 1)
    const min = 0
    const padX = 2
    const padY = 6
    const span = points.length === 1 ? 1 : points.length - 1
    const xStep = (width - padX * 2) / span
    const yScale = (height - padY * 2) / Math.max(max - min, 1)
    const xy = points.map((p, i) => ({
      x: padX + i * xStep,
      y: height - padY - (p.value - min) * yScale,
    }))

    // Catmull-Rom → cubic Bezier smoothing for a natural curve.
    const smooth = (tension = 0.5) => {
      if (xy.length < 2) return `M${xy[0].x},${xy[0].y}`
      let d = `M${xy[0].x},${xy[0].y}`
      for (let i = 0; i < xy.length - 1; i++) {
        const p0 = xy[i - 1] ?? xy[i]
        const p1 = xy[i]
        const p2 = xy[i + 1]
        const p3 = xy[i + 2] ?? p2
        const c1x = p1.x + ((p2.x - p0.x) / 6) * tension
        const c1y = p1.y + ((p2.y - p0.y) / 6) * tension
        const c2x = p2.x - ((p3.x - p1.x) / 6) * tension
        const c2y = p2.y - ((p3.y - p1.y) / 6) * tension
        d += ` C${c1x.toFixed(2)},${c1y.toFixed(2)} ${c2x.toFixed(2)},${c2y.toFixed(2)} ${p2.x.toFixed(2)},${p2.y.toFixed(2)}`
      }
      return d
    }

    const line = smooth()
    const baseY = height - padY
    const area =
      `M${xy[0].x},${baseY} L${xy[0].x},${xy[0].y} ` +
      line.slice(line.indexOf(' ')) +
      ` L${xy[xy.length - 1].x},${baseY} Z`
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
          id={gradientId}
          x1="0"
          y1="0"
          x2="0"
          y2="1"
        >
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.55" />
          <stop offset="55%" stopColor="currentColor" stopOpacity="0.18" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
        <filter
          id={glowId}
          x="-20%"
          y="-50%"
          width="140%"
          height="200%"
        >
          <feGaussianBlur stdDeviation="1.4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <path d={path.area} fill={`url(#${gradientId})`} />
      <path
        d={path.line}
        className="rp-sparkline__line"
        filter={`url(#${glowId})`}
      />
      {path.last && (
        <g className="rp-sparkline__last">
          <circle
            cx={path.last.x}
            cy={path.last.y}
            r={6}
            className="rp-sparkline__halo"
          />
          <circle
            cx={path.last.x}
            cy={path.last.y}
            r={3.5}
            className="rp-sparkline__dot"
          />
        </g>
      )}
    </svg>
  )
}
