interface Props {
  rows: string[]
  cols: string[]
  values: number[][]
  ariaLabel?: string
  cellSize?: number
}

function colorForRatio(ratio: number): string {
  const clamped = Math.max(0, Math.min(1, ratio))
  const alpha = 0.08 + clamped * 0.7
  return `color-mix(in srgb, var(--accent) ${alpha * 100}%, transparent)`
}

export function Heatmap({
  rows,
  cols,
  values,
  ariaLabel,
  cellSize = 28,
}: Props) {
  let max = 0
  for (const row of values) {
    for (const v of row) {
      if (v > max) max = v
    }
  }
  return (
    <div
      className="admin-heatmap"
      role="img"
      aria-label={ariaLabel}
    >
      <table className="admin-heatmap__table">
        <thead>
          <tr>
            <th />
            {cols.map((col) => (
              <th
                key={col}
                className="admin-heatmap__col-label"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={row}>
              <th className="admin-heatmap__row-label">
                {row}
              </th>
              {cols.map((col, ci) => {
                const value =
                  values[ri]?.[ci] ?? 0
                const ratio =
                  max > 0 ? value / max : 0
                return (
                  <td
                    key={col}
                    title={`${row} · ${col}: ${value}`}
                    className="admin-heatmap__cell"
                    style={{
                      width: cellSize,
                      height: cellSize,
                      background:
                        colorForRatio(ratio),
                    }}
                  >
                    <span className="admin-heatmap__value">
                      {value || ''}
                    </span>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
