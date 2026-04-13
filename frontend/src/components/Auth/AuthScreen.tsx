import { useState } from 'react'
import { EmailAuth } from './EmailAuth'
import { TelegramAuth } from './TelegramAuth'

type Method = 'choose' | 'telegram' | 'email'

interface Props {
  onAuth: () => void
}

export function AuthScreen({ onAuth }: Props) {
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
          Добро пожаловать
        </h2>
        <p className="auth-hint">
          Музыка без рекламы.
          <br />
          Слушай. Делись. Открывай.
        </p>
        <button
          className="btn-primary auth-tg-btn"
          onClick={() => setMethod('telegram')}
        >
          Войти через Telegram
        </button>
        <button
          className="btn-secondary auth-back"
          onClick={() => setMethod('email')}
        >
          Войти по email
        </button>
      </div>
    </div>
  )
}
