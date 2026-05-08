import type { CSSProperties } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { useTranslation } from 'react-i18next'

interface PullState {
  pulling: boolean
  armed: boolean
  distance: number
  refreshing: boolean
}

interface Props {
  state: PullState
  /** Optional label override (e.g. localized "Pull to refresh"). */
  label?: string
  className?: string
}

/**
 * Visual companion to `usePullToRefresh`. Renders a glass pill at
 * the top of the viewport whose progress / armed / refreshing
 * states are derived from the hook output. Pure presentational.
 *
 * Mount it once at the top of any view that uses the hook so the
 * pill is portal-free and lives inside the view itself.
 */
export function PullToRefreshIndicator({
  state,
  label,
  className,
}: Props) {
  const { t } = useTranslation()
  if (!state.pulling && !state.refreshing) return null

  const ptrState = state.refreshing
    ? 'refreshing'
    : state.armed
      ? 'armed'
      : 'pulling'

  const style = {
    ['--ptr-pull' as string]: `${Math.min(state.distance, 96)}px`,
  } as CSSProperties

  const text = state.refreshing
    ? (label ?? t('redesign.home.ptrRefresh', 'Refreshing…'))
    : state.armed
      ? t('redesign.home.ptrRelease', 'Release')
      : (label ?? t('redesign.home.ptrPull', 'Pull down'))

  const cls = ['ptr-indicator', className]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      className={cls}
      data-ptr-state={ptrState}
      style={style}
      aria-hidden
    >
      <span className="ptr-indicator__icon">
        <Icon name="refresh" size={14} />
      </span>
      <span>{text}</span>
    </div>
  )
}
