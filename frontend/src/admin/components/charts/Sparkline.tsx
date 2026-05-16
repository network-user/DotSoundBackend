interface Props {
  data: number[]
  height?: number
  ariaLabel?: string
}

const WIDTH = 140

function pathFor(values: number[], height: number): string {
  const clean = values.filter(Number.isFinite)
  if (clean.length === 0) return ''
  const min = Math.min(...clean)
  const max = Math.max(...clean)
  const range = max - min || 1
  return clean
    .map((value, i) => {
      const x =
        clean.length === 1
          ? WIDTH / 2
          : (i / (clean.length - 1)) * WIDTH
      const y =
        height - ((value - min) / range) * (height - 4) - 2
      return `${i === 0 ? 'M' : 'L'}${x},${y}`
    })
    .join(' ')
}

export function Sparkline({
  data,
  height = 32,
  ariaLabel,
}: Props) {
  const path = pathFor(data, height)
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
      {path ? (
        <svg
          viewBox={`0 0 ${WIDTH} ${height}`}
          width="100%"
          height={height}
        >
          <path
            d={path}
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      ) : null}
    </span>
  )
}
