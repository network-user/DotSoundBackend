import { Icon } from '@/components/Icon/Icon'
import { useBrandLabel } from '@/lib/brand'

interface Props {
  reason?: string | null
  onContact?: () => void
  onLogout?: () => void
}

export function BannedScreen({
  reason,
  onContact,
  onLogout,
}: Props) {
  const brandLabel = useBrandLabel()
  return (
    <div
      className="banned-screen"
      role="alert"
      aria-live="assertive"
    >
      <div className="banned-screen__card">
        <div className="banned-screen__icon">
          <Icon name="shield" size={36} />
        </div>
        <h1 className="banned-screen__title">
          Аккаунт заблокирован
        </h1>
        <p className="banned-screen__hint">
          Доступ к {brandLabel} временно ограничен
          администрацией.
          {reason ? ` Причина: ${reason}.` : ''}
        </p>
        <p className="banned-screen__hint banned-screen__hint--muted">
          Если считаете, что это ошибка, напишите
          в поддержку.
        </p>
        <div className="banned-screen__actions">
          {onContact && (
            <button
              type="button"
              className="banned-screen__btn primary"
              onClick={onContact}
            >
              <Icon
                name="message-circle"
                size={16}
              />
              Связаться с поддержкой
            </button>
          )}
          {onLogout && (
            <button
              type="button"
              className="banned-screen__btn"
              onClick={onLogout}
            >
              <Icon name="log-out" size={16} />
              Выйти
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
