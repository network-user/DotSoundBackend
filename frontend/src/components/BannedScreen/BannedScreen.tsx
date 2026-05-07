import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { useBrandLabel } from '@/lib/brand'
import { MotionPress } from '@/components/ui/MotionPress'

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
  const { t } = useTranslation()
  const brandLabel = useBrandLabel()
  return (
    <div
      className="banned-screen rb-ban"
      role="alert"
      aria-live="assertive"
    >
      <div className="banned-screen__card rb-ban__card glass--strong">
        <div className="banned-screen__icon">
          <Icon name="lock" size={36} />
        </div>
        <h1 className="banned-screen__title">
          {t(
            'redesign.nav.bannedTitle',
            'Account blocked',
          )}
        </h1>
        <p className="banned-screen__hint">
          {t('redesign.nav.bannedHint', {
            brand: brandLabel,
            defaultValue:
              'Access to {{brand}} is temporarily restricted.',
          })}
          {reason ? ` ${reason}` : ''}
        </p>
        <p className="banned-screen__hint banned-screen__hint--muted">
          {t(
            'redesign.nav.bannedSupport',
            'If this is a mistake, contact support.',
          )}
        </p>
        <div className="banned-screen__actions">
          {onContact && (
            <MotionPress
              variant="primary"
              className="banned-screen__btn primary"
              haptic="medium"
              onClick={onContact}
            >
              <Icon
                name="message-circle"
                size={16}
              />
              {t(
                'redesign.nav.bannedContact',
                'Contact support',
              )}
            </MotionPress>
          )}
          {onLogout && (
            <MotionPress
              variant="ghost"
              className="banned-screen__btn"
              haptic="light"
              onClick={onLogout}
            >
              <Icon name="log-out" size={16} />
              {t(
                'redesign.nav.bannedLogout',
                'Log out',
              )}
            </MotionPress>
          )}
        </div>
      </div>
    </div>
  )
}
