import { useId } from 'react'

export interface ChartPoint {
  ts: number
  value: number
}

interface Props {
  data: ChartPoint[]
  height?: number
  ariaLabel?: string
}

const WIDTH = 640
const PAD_LEFT = 46
const PAD_RIGHT = 16
const PAD_TOP = 12
const PAD_BOTTOM = 28

function formatTime(value: number): string {
  return new Date(value * 1000).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatValue(value: number): string {
  const abs = Math.abs(value)
  if (abs >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}m`
  }
  if (abs >= 1_000) {
    return `${(value / 1_000).toFixed(1)}k`
  }
  if (abs >= 100) return value.toFixed(0)
  if (abs >= 10) return value.toFixed(1)
  return value.toFixed(2)
}

function finitePoints(data: ChartPoint[]): ChartPoint[] {
  return data.filter(
    (p) =>
      Number.isFinite(p.ts) &&
      Number.isFinite(p.value),
  )
}

export function LineChart({
  data,
  height = 220,
  ariaLabel,
}: Props) {
  const gradientId = useId().replace(/:/g, '')
  const points = finitePoints(data)
  if (points.length === 0) {
    return (
      <div
        className="admin-chart"
        role="img"
        aria-label={ariaLabel}
      >
        <div
          className="admin-log-empty"
          style={{ minHeight: height }}
        />
      </div>
    )
  }

  const plotWidth = WIDTH - PAD_LEFT - PAD_RIGHT
  const plotHeight = height - PAD_TOP - PAD_BOTTOM
  const xMin = Math.min(...points.map((p) => p.ts))
  const xMax = Math.max(...points.map((p) => p.ts))
  const yRawMin = Math.min(...points.map((p) => p.value))
  const yRawMax = Math.max(...points.map((p) => p.value))
  const ySpread = yRawMax - yRawMin
  const yPad =
    ySpread === 0
      ? Math.max(1, Math.abs(yRawMax) * 0.08)
      : ySpread * 0.08
  const yMin = yRawMin - yPad
  const yMax = yRawMax + yPad
  const yRange = yMax - yMin || 1
  const xRange = xMax - xMin || 1

  const xy = points.map((p) => ({
    x: PAD_LEFT + ((p.ts - xMin) / xRange) * plotWidth,
    y:
      PAD_TOP +
      plotHeight -
      ((p.value - yMin) / yRange) * plotHeight,
  }))
  const linePath = xy
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`)
    .join(' ')
  const areaPath =
    xy.length > 0
      ? `${linePath} L${xy[xy.length - 1].x},${PAD_TOP + plotHeight} L${
          xy[0].x
        },${PAD_TOP + plotHeight} Z`
      : ''
  const yTicks = Array.from({ length: 4 }, (_, i) => {
    const value = yMin + (yRange * i) / 3
    return {
      value,
      y:
        PAD_TOP +
        plotHeight -
        ((value - yMin) / yRange) * plotHeight,
    }
  }).reverse()

  return (
    <div
      className="admin-chart"
      role="img"
      aria-label={ariaLabel}
    >
      <svg
        className="admin-line-chart"
        viewBox={`0 0 ${WIDTH} ${height}`}
        width="100%"
        height={height}
      >
        <defs>
          <linearGradient
            id={gradientId}
            x1="0"
            y1="0"
            x2="0"
            y2="1"
          >
            <stop
              offset="0%"
              stopColor="currentColor"
              stopOpacity={0.24}
            />
            <stop
              offset="100%"
              stopColor="currentColor"
              stopOpacity={0}
            />
          </linearGradient>
        </defs>
        <g className="admin-chart__grid" aria-hidden>
          {yTicks.map((tick) => (
            <g key={tick.value}>
              <line
                x1={PAD_LEFT}
                x2={WIDTH - PAD_RIGHT}
                y1={tick.y}
                y2={tick.y}
              />
              <text
                x={PAD_LEFT - 8}
                y={tick.y + 4}
                textAnchor="end"
              >
                {formatValue(tick.value)}
              </text>
            </g>
          ))}
        </g>
        <path d={areaPath} fill={`url(#${gradientId})`} />
        <path
          d={linePath}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
        <g className="admin-chart__axis" aria-hidden>
          <text
            x={PAD_LEFT}
            y={height - 8}
            textAnchor="start"
          >
            {formatTime(xMin)}
          </text>
          <text
            x={WIDTH - PAD_RIGHT}
            y={height - 8}
            textAnchor="end"
          >
            {formatTime(xMax)}
          </text>
        </g>
      </svg>
    </div>
  )
}
