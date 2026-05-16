import { useId } from 'react'

export interface MultiSeriesPoint {
  ts: number
  [series: string]: number
}

interface Props {
  data: MultiSeriesPoint[]
  series: string[]
  height?: number
  ariaLabel?: string
  stacked?: boolean
}

const WIDTH = 640
const PAD_LEFT = 46
const PAD_RIGHT = 16
const PAD_TOP = 12
const PAD_BOTTOM = 32

function formatTime(value: number): string {
  return new Date(value * 1000).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatValue(value: number): string {
  const abs = Math.abs(value)
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)}k`
  if (abs >= 100) return value.toFixed(0)
  if (abs >= 10) return value.toFixed(1)
  return value.toFixed(2)
}

function valueAt(
  item: MultiSeriesPoint,
  name: string,
): number {
  const value = item[name]
  return Number.isFinite(value) ? value : 0
}

export function AreaChart({
  data,
  series,
  height = 240,
  ariaLabel,
  stacked = false,
}: Props) {
  const idSeed = useId().replace(/:/g, '')
  const clean = data.filter((p) => Number.isFinite(p.ts))
  if (clean.length === 0 || series.length === 0) {
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
  const xMin = Math.min(...clean.map((p) => p.ts))
  const xMax = Math.max(...clean.map((p) => p.ts))
  const xRange = xMax - xMin || 1
  const values = clean.flatMap((item) => {
    if (!stacked) {
      return series.map((name) => valueAt(item, name))
    }
    let total = 0
    return series.map((name) => {
      total += valueAt(item, name)
      return total
    })
  })
  const yRawMin = Math.min(0, ...values)
  const yRawMax = Math.max(1, ...values)
  const yRange = yRawMax - yRawMin || 1
  const yTicks = Array.from({ length: 4 }, (_, i) => {
    const value = yRawMin + (yRange * i) / 3
    return {
      value,
      y:
        PAD_TOP +
        plotHeight -
        ((value - yRawMin) / yRange) * plotHeight,
    }
  }).reverse()

  const seriesPaths = series.map((name, index) => {
    const points = clean.map((item) => {
      const value = valueAt(item, name)
      const displayValue = stacked
        ? series
            .slice(0, index + 1)
            .reduce(
              (sum, itemName) =>
                sum + valueAt(item, itemName),
              0,
            )
        : value
      return {
        x:
          PAD_LEFT +
          ((item.ts - xMin) / xRange) * plotWidth,
        y:
          PAD_TOP +
          plotHeight -
          ((displayValue - yRawMin) / yRange) *
            plotHeight,
      }
    })
    const line = points
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`)
      .join(' ')
    const bottom = PAD_TOP + plotHeight
    const area =
      points.length > 0
        ? `${line} L${points[points.length - 1].x},${bottom} L${
            points[0].x
          },${bottom} Z`
        : ''
    return {
      name,
      line,
      area,
      gradientId: `${idSeed}-${index}`,
      opacity: Math.max(0.28, 0.72 - index * 0.12),
    }
  })

  return (
    <div
      className="admin-chart"
      role="img"
      aria-label={ariaLabel}
    >
      <svg
        className="admin-area-chart"
        viewBox={`0 0 ${WIDTH} ${height}`}
        width="100%"
        height={height}
      >
        <defs>
          {seriesPaths.map((item) => (
            <linearGradient
              key={item.gradientId}
              id={item.gradientId}
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop
                offset="0%"
                stopColor="currentColor"
                stopOpacity={0.18}
              />
              <stop
                offset="100%"
                stopColor="currentColor"
                stopOpacity={0}
              />
            </linearGradient>
          ))}
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
        {seriesPaths.map((item) => (
          <g key={item.name} opacity={item.opacity}>
            <path
              d={item.area}
              fill={`url(#${item.gradientId})`}
            />
            <path
              d={item.line}
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              vectorEffect="non-scaling-stroke"
            />
          </g>
        ))}
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
