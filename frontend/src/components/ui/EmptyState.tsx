import type { ReactNode } from 'react'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  icon?: string
  title: string
  hint?: string
  action?: ReactNode
}

export function EmptyState({
  icon = 'empty-staff',
  title,
  hint,
  action,
}: Props) {
  return (
    <div
      className="empty-state-card"
      role="status"
    >
      <span className="empty-icon">
        <Icon name={icon} size={28} />
      </span>
      <span className="empty-title">{title}</span>
      {hint && (
        <span className="empty-hint">{hint}</span>
      )}
      {action}
    </div>
  )
}
