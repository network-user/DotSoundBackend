import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  hasAbuseConsent,
  setAbuseConsent,
} from '@/lib/clientSignals'

const COOKIE_KEY = 'cookie_notice_dismissed'
const COOKIE_VALUE = 'v1'

function bothFlagsSet(): boolean {
  try {
    const consentSeen =
      localStorage.getItem('ds_consent_v1') !== null
    const cookieSeen =
      localStorage.getItem(COOKIE_KEY) === COOKIE_VALUE
    return consentSeen && cookieSeen
  } catch {
    return true
  }
}

function persistCookieFlag(): void {
  try {
    localStorage.setItem(COOKIE_KEY, COOKIE_VALUE)
  } catch {
    /* ignore */
  }
}

/**
 * Единое уведомление об обработке данных: cookies / localStorage,
 * нужные для работы сервиса, плюс минимальные сигналы против
 * автоматических регистраций. Две ссылки на документы, две кнопки:
 * «Принять» включает сигналы анти-абьюза, «Только необходимое»
 * оставляет лишь технические cookies.
 */
export function ConsentBanner() {
  const { t } = useTranslation()
  const [decided, setDecided] = useState(true)

  useEffect(() => {
    setDecided(bothFlagsSet())
  }, [])

  if (decided) return null

  const choose = (accept: boolean) => {
    setAbuseConsent(accept)
    persistCookieFlag()
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
          {t('consent.title', 'Обработка данных и защита аккаунта')}
        </h2>
        <p className="consent-banner__text">
          {t(
            'consent.body',
            'DotSound использует localStorage и cookies, нужные для авторизации, настроек плеера и темы. Рекламных и сторонних аналитических трекеров нет. Дополнительно подключаем минимальные сигналы против автоматических регистраций, связанные записи храним до 30 дней.',
          )}
        </p>
        <p className="consent-banner__links">
          <Link
            className="consent-banner__agreement"
            to="/legal/privacy"
          >
            {t('consent.privacyLink', 'Политика конфиденциальности')}
          </Link>
          <span className="consent-banner__sep" aria-hidden>
            ·
          </span>
          <Link
            className="consent-banner__agreement"
            to="/legal/anti-abuse-signals"
          >
            {t('consent.agreementLink', 'Сигналы против ботов')}
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
