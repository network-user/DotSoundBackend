import {
  Line,
  LineChart as RechartsLineChart,
  ResponsiveContainer,
  YAxis,
} from 'recharts'

export interface SparkPoint {
  v: number
}

interface Props {
  data: number[]
  height?: number
  ariaLabel?: string
}

export function Sparkline({
  data,
  height = 32,
  ariaLabel,
}: Props) {
  const points: SparkPoint[] = data.map((v) => ({
    v,
  }))
  return (
    <span
      className="admin-sparkline"
      role="img"
      aria-label={ariaLabel}
      style={{
        display: 'inline-block',
        width: '100%',
        minWidth: 60,
        height,
        color: 'var(--accent)',
      }}
    >
      <ResponsiveContainer
        width="100%"
        height={height}
      >
        <RechartsLineChart
          data={points}
          margin={{
            top: 2,
            right: 2,
            bottom: 2,
            left: 2,
          }}
        >
          <YAxis hide domain={['auto', 'auto']} />
          <Line
            type="monotone"
            dataKey="v"
            stroke="currentColor"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </RechartsLineChart>
      </ResponsiveContainer>
    </span>
  )
}
