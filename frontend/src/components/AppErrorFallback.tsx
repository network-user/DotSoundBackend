import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'

type Props = {
  variant: 'crash' | 'section'
  onPrimary: () => void
}

export function AppErrorFallback({
  variant,
  onPrimary,
}: Props) {
  const { t } = useTranslation()
  const title =
    variant === 'crash'
      ? t('app.errorTitle')
      : t('app.sectionLoadError')
  const hint =
    variant === 'crash'
      ? t('app.errorHint')
      : t('app.sectionLoadHint')
  const action =
    variant === 'crash'
      ? t('app.tryAgain')
      : t('app.reload')

  const panel = (
    <div className="app-issue-overlay" role="presentation">
      <div className="app-issue-panel" role="alert">
        <div
          className="app-issue-panel__icon"
          aria-hidden
        >
          <Icon
            name="alert-triangle"
            size={28}
          />
        </div>
        <h1 className="app-issue-panel__title">
          {title}
        </h1>
        <p className="app-issue-panel__hint">{hint}</p>
        <button
          type="button"
          className="mp-press mp-press--primary app-issue-panel__btn"
          onClick={onPrimary}
        >
          {action}
        </button>
      </div>
    </div>
  )

  if (typeof document !== 'undefined') {
    return createPortal(panel, document.body)
  }
  return panel
}
