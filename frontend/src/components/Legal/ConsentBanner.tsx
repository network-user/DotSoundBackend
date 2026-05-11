import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
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
      aria-modal="false"
      aria-labelledby="consent-banner-title"
      aria-live="polite"
    >
      <div className="consent-banner__shell">
        <h2
          id="consent-banner-title"
          className="consent-banner__title"
        >
          {t('consent.title', 'Защита от автоматических регистраций')}
        </h2>
        <p className="consent-banner__text">
          {t(
            'consent.body',
            'Подключаем минимальную аналитику только против ' +
              'автоматических регистраций; связанные записи храним ' +
              'до 30 дней. Рекламы нет, передачи этих сигналов ' +
              'третьим лицам для маркетинга тоже нет. ',
          )}
          <Link
            className="consent-banner__agreement"
            to="/legal/anti-abuse-signals"
          >
            {t(
              'consent.agreementLink',
              'Текст соглашения',
            )}
          </Link>
        </p>
        <div className="consent-banner__actions">
          <MotionPress
            type="button"
            variant="primary"
            haptic="medium"
            className="consent-banner__btn consent-banner__btn--primary"
            onClick={() => {
              choose(true)
              void hasAbuseConsent()
            }}
          >
            {t('consent.accept', 'Принять')}
          </MotionPress>
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="consent-banner__btn consent-banner__btn--secondary"
            onClick={() => choose(false)}
          >
            {t('consent.minimal', 'Только необходимое')}
          </MotionPress>
        </div>
      </div>
    </div>
  )
}
