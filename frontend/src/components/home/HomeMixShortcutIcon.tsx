import type { ReactNode } from 'react'

export type HomeMixShortcutIconId =
  | 'mix-daily'
  | 'mix-weekly'
  | 'mix-top'
  | 'mix-trending'
  | 'mix-forgotten'
  | 'mix-personal'

interface HomeMixShortcutIconProps {
  id: HomeMixShortcutIconId
  size?: number
  className?: string
}

const STROKE = 1.75

function IconShell({
  size,
  className,
  children,
}: {
  size: number
  className?: string
  children: ReactNode
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      fill="none"
      stroke="currentColor"
      strokeWidth={STROKE}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {children}
    </svg>
  )
}

export function HomeMixShortcutIcon({
  id,
  size = 24,
  className,
}: HomeMixShortcutIconProps) {
  switch (id) {
    case 'mix-daily':
      return (
        <IconShell size={size} className={className}>
          <circle cx="8.5" cy="8.5" r="3.5" />
          <path d="M8.5 5.5V4M8.5 13v1.5M5.5 8.5H4M13 8.5h1.5" />
          <path d="M14.5 14.5v5M17 17h-5M19.5 14.5v5M22 17h-5" />
        </IconShell>
      )
    case 'mix-weekly':
      return (
        <IconShell size={size} className={className}>
          <circle cx="12" cy="12" r="7.25" />
          <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
          <path d="M12 4.75V6.5M12 17.5v1.75M4.75 12H6.5M17.5 12h1.75" />
          <path d="M7.1 7.1l1.24 1.24M15.66 15.66l1.24 1.24M16.9 7.1l-1.24 1.24M8.34 15.66l-1.24 1.24" />
        </IconShell>
      )
    case 'mix-top':
      return (
        <IconShell size={size} className={className}>
          <path d="M5 20h14" />
          <path d="M7.5 20V13.5l3-4.5 3 2.5 3.5-5.5V20" />
          <path d="M12 4.5l1.35 2.7 3 .45-2.17 2.1.51 2.98L12 11.2" />
        </IconShell>
      )
    case 'mix-trending':
      return (
        <IconShell size={size} className={className}>
          <path d="M4 18V9.5M9 18V6.5M14 18v-5.5M19 18V4" />
          <path d="M16.5 5.5L19 4l1.5 2.5" />
          <path d="M19 4v3.5" />
        </IconShell>
      )
    case 'mix-forgotten':
      return (
        <IconShell size={size} className={className}>
          <path d="M12 8v4l2.5 2.5" />
          <path d="M7.5 7.5A6.5 6.5 0 0118.2 12" />
          <path d="M16.5 16.5A6.5 6.5 0 015.8 12" />
          <path d="M12 5.5V4M9.2 6.3l-1.2-1.2M14.8 6.3l1.2-1.2" />
        </IconShell>
      )
    case 'mix-personal':
      return (
        <IconShell size={size} className={className}>
          <path d="M6 18v-4.5a2.2 2.2 0 012.2-2.2h1.3" />
          <circle cx="9.5" cy="8.2" r="2.2" />
          <path d="M13.5 10.5l5.5-2.2-2.2 5.5-3.3 1.1-1.1 3.3z" />
        </IconShell>
      )
  }
}
