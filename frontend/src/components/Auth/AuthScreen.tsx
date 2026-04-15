import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { EmailAuth } from './EmailAuth'
import { TelegramAuth } from './TelegramAuth'

type Method = 'choose' | 'telegram' | 'email'

interface Props {
  onAuth: () => void
  error?: string | null
  debugInfo?: Record<string, string>
}

function DebugOverlay({
  info,
  error,
}: {
  info: Record<string, string>
  error?: string | null
}) {
  const entries = Object.entries(info)
  if (!entries.length && !error) return null

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 12,
        left: 12,
        right: 12,
        background: 'rgba(0,0,0,0.85)',
        border: '1px solid rgba(255,255,255,0.15)',
        borderRadius: 8,
        padding: '10px 12px',
        fontFamily: 'monospace',
        fontSize: 11,
        lineHeight: 1.6,
        color: 'rgba(255,255,255,0.7)',
        zIndex: 9999,
        wordBreak: 'break-all',
        maxHeight: '40vh',
        overflow: 'auto',
      }}
    >
      <div
        style={{
          color: 'rgba(255,255,255,0.35)',
          fontSize: 10,
          marginBottom: 4,
        }}
      >
        DEBUG
      </div>
      {entries.map(([k, v]) => (
        <div key={k}>
          <span
            style={{
              color: 'rgba(255,255,255,0.4)',
            }}
          >
            {k}:{' '}
          </span>
          {v}
        </div>
      ))}
      {error && (
        <div style={{ color: '#e55' }}>
          error: {error}
        </div>
      )}
    </div>
  )
}

export function AuthScreen({
  onAuth,
  error,
  debugInfo,
}: Props) {
  const { t } = useTranslation()
  const [showDebug, setShowDebug] =
    useState(import.meta.env.DEV)

  useEffect(() => {
    if (showDebug) return
    api
      .getAuthConfig()
      .then((cfg) => {
        if (cfg.debug) {
          setShowDebug(true)
        }
      })
      .catch(() => {})
  }, [showDebug])

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
        {error && (
          <p
            className="auth-error"
            style={{
              marginTop: 16,
              fontSize: 13,
              opacity: 0.8,
              wordBreak: 'break-all',
              color: '#e55',
            }}
          >
            {error}
          </p>
        )}
      </div>
      {showDebug && debugInfo && (
        <DebugOverlay
          info={debugInfo}
          error={error}
        />
      )}
    </div>
  )
}
