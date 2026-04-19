import {
  Area,
  AreaChart as RechartsAreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

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

const fmtTime = (v: number) =>
  new Date(v * 1000).toLocaleTimeString()

export function AreaChart({
  data,
  series,
  height = 240,
  ariaLabel,
  stacked = false,
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
        <RechartsAreaChart
          data={data}
          margin={{
            top: 12,
            left: 12,
            right: 12,
            bottom: 12,
          }}
        >
          <defs>
            {series.map((name, idx) => (
              <linearGradient
                key={name}
                id={`admin-area-${idx}`}
                x1="0"
                y1="0"
                x2="0"
                y2="1"
              >
                <stop
                  offset="0%"
                  stopColor="currentColor"
                  stopOpacity={
                    0.3 - idx * 0.05
                  }
                />
                <stop
                  offset="100%"
                  stopColor="currentColor"
                  stopOpacity={0}
                />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid
            stroke="var(--border)"
            strokeDasharray="3 3"
          />
          <XAxis
            dataKey="ts"
            stroke="var(--text-secondary)"
            tickFormatter={fmtTime}
            minTickGap={32}
          />
          <YAxis stroke="var(--text-secondary)" />
          <Tooltip
            contentStyle={{
              background: 'var(--surface-2)',
              border:
                '1px solid var(--border)',
              borderRadius: 'var(--r-md)',
              color: 'var(--text)',
            }}
            labelFormatter={fmtTime}
          />
          <Legend />
          {series.map((name, idx) => (
            <Area
              key={name}
              type="monotone"
              dataKey={name}
              stackId={
                stacked ? 'a' : undefined
              }
              stroke="currentColor"
              strokeOpacity={1 - idx * 0.15}
              fill={`url(#admin-area-${idx})`}
              strokeWidth={2}
            />
          ))}
        </RechartsAreaChart>
      </ResponsiveContainer>
    </div>
  )
}
