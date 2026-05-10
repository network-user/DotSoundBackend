import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  hasAbuseConsent,
  setAbuseConsent,
} from '@/lib/clientSignals'

export function ConsentBanner() {
  const { t } = useTranslation()
  const [decided, setDecided] = useState(true)

  useEffect(() => {
    try {
      const seen =
        localStorage.getItem('ds_consent_v1') !== null
      setDecided(seen)
    } catch {
      setDecided(true)
    }
  }, [])

  if (decided) return null

  const choose = (accept: boolean) => {
    setAbuseConsent(accept)
    setDecided(true)
  }

  return (
    <div
      className="consent-banner"
      role="dialog"
      aria-live="polite"
    >
      <p className="consent-banner__text">
        {t(
          'consent.body',
          'Мы используем минимальную аналитику только для защиты ' +
            'от автоматических регистраций (срок хранения — до ' +
            '30 дней). Реклама и третьи лица — нет.',
        )}
      </p>
      <div className="consent-banner__actions">
        <MotionPress
          type="button"
          variant="primary"
          haptic="medium"
          className="btn-primary"
          onClick={() => {
            choose(true)
            // re-export so future requests pick up consent
            void hasAbuseConsent()
          }}
        >
          {t('consent.accept', 'Принять')}
        </MotionPress>
        <MotionPress
          type="button"
          variant="ghost"
          haptic="light"
          className="btn-secondary"
          onClick={() => choose(false)}
        >
          {t('consent.minimal', 'Только необходимое')}
        </MotionPress>
      </div>
    </div>
  )
}
