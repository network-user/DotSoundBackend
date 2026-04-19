import { ReactNode } from 'react'

interface Props {
  label: string
  value: ReactNode
  hint?: ReactNode
  accent?: 'default' | 'warn' | 'error'
}

export function KpiCard({
  label,
  value,
  hint,
  accent = 'default',
}: Props) {
  return (
    <div className={`kpi-card kpi-card--${accent}`}>
      <div className="kpi-card__label">{label}</div>
      <div className="kpi-card__value">{value}</div>
      {hint && (
        <div className="kpi-card__hint">{hint}</div>
      )}
    </div>
  )
}
