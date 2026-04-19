import { ReactNode } from 'react'

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

export function StatusPill({
  kind,
  children,
  title,
}: Props) {
  return (
    <span
      className={`status-pill status-pill--${kind}`}
      role="status"
      title={title}
    >
      <span
        className={`status-pill__dot status-pill__dot--${kind}`}
        aria-hidden="true"
      />
      {children}
    </span>
  )
}
