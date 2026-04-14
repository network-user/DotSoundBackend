import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { EmailAuth } from './EmailAuth'
import { TelegramAuth } from './TelegramAuth'

type Method = 'choose' | 'telegram' | 'email'

interface Props {
  onAuth: () => void
}

export function AuthScreen({ onAuth }: Props) {
  const { t } = useTranslation()
  const params = new URLSearchParams(
    window.location.search,
  )
  const hasToken = params.has('token')
  const hasAuthCode =
    params.get('auth') === 'code'
  const initial: Method = hasToken
    ? 'email'
    : hasAuthCode
      ? 'telegram'
      : 'choose'

  const [method, setMethod] =
    useState<Method>(initial)

  if (method === 'telegram') {
    return (
      <TelegramAuth
        onAuth={onAuth}
        onEmail={() => setMethod('email')}
      />
    )
  }

  if (method === 'email') {
    return (
      <EmailAuth
        onAuth={onAuth}
        onBack={() => setMethod('choose')}
      />
    )
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-logo">.sound</div>
        <h2 className="auth-title">
          {t('auth.welcome')}
        </h2>
        <p className="auth-hint">
          {t('auth.tagline')}
          <br />
          {t('auth.subtitle')}
        </p>
        <button
          className="btn-primary auth-tg-btn"
          onClick={() => setMethod('telegram')}
        >
          {t('auth.loginTelegram')}
        </button>
        <button
          className="btn-secondary auth-back"
          onClick={() => setMethod('email')}
        >
          {t('auth.loginEmail')}
        </button>
      </div>
    </div>
  )
}
