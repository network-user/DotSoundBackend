import { ReactNode } from 'react'
import { Icon } from '@/components/Icon/Icon'

export type StatusKind =
  | 'ok'
  | 'warn'
  | 'error'
  | 'unknown'

interface Props {
  kind: StatusKind
  children: ReactNode
  title?: string
}

const ICON_FOR_KIND: Record<StatusKind, string> = {
  ok: 'circle',
  warn: 'alert-triangle',
  error: 'x',
  unknown: 'info',
}

export function StatusPill({
  kind,
  children,
  title,
}: Props) {
  return (
    <span
      className={`status-pill status-pill--${kind} adm-r-status-pill`}
      role="status"
      title={title}
    >
      <span
        className="adm-r-status-pill__icon"
        aria-hidden="true"
      >
        <Icon name={ICON_FOR_KIND[kind]} size={12} />
      </span>
      {children}
    </span>
  )
}
