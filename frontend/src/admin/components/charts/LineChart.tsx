import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export interface ChartPoint {
  ts: number
  value: number
}

interface Props {
  data: ChartPoint[]
  height?: number
  ariaLabel?: string
}

const fmt = (v: number) =>
  new Date(v * 1000).toLocaleTimeString()

export function LineChart({
  data,
  height = 220,
  ariaLabel,
}: Props) {
  return (
    <div
      className="admin-chart"
      role="img"
      aria-label={ariaLabel}
    >
      <ResponsiveContainer
        width="100%"
        height={height}
      >
        <AreaChart
          data={data}
          margin={{
            top: 12,
            left: 12,
            right: 12,
            bottom: 12,
          }}
        >
          <defs>
            <linearGradient
              id="admin-chart-fill"
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop
                offset="0%"
                stopColor="currentColor"
                stopOpacity={0.4}
              />
              <stop
                offset="100%"
                stopColor="currentColor"
                stopOpacity={0}
              />
            </linearGradient>
          </defs>
          <CartesianGrid
            stroke="var(--border)"
            strokeDasharray="3 3"
          />
          <XAxis
            dataKey="ts"
            stroke="var(--text-secondary)"
            tickFormatter={fmt}
            minTickGap={32}
          />
          <YAxis
            stroke="var(--text-secondary)"
          />
          <Tooltip
            contentStyle={{
              background: 'var(--surface-2)',
              border:
                '1px solid var(--border)',
              borderRadius: 'var(--r-md)',
              color: 'var(--text)',
            }}
            labelFormatter={fmt}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="currentColor"
            fill="url(#admin-chart-fill)"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
