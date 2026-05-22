import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { useBrandLabel } from '@/lib/brand'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MotionPress } from '@/components/ui/MotionPress'
import { EmailAuth } from './EmailAuth'
import { TelegramAuth } from './TelegramAuth'

const AUTH_KB_SRC =
  'data:image/svg+xml,' +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24'>" +
      "<defs>" +
      "<linearGradient id='a' x1='0' y1='0' x2='1' y2='1'>" +
      "<stop offset='0' stop-color='%23222'/>" +
      "<stop offset='1' stop-color='%23383838'/>" +
      '</linearGradient></defs>' +
      "<rect width='24' height='24' fill='url(%23a)'/></svg>",
  )

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
  const brandLabel = useBrandLabel()
  const [showDebug, setShowDebug] =
    useState(import.meta.env.DEV)
  const [botUsername, setBotUsername] = useState('')
  const [configReady, setConfigReady] =
    useState(false)
  const [configError, setConfigError] = useState('')
  const [popupBlocked, setPopupBlocked] =
    useState(false)
  const [telegramStartStep, setTelegramStartStep] =
    useState<'welcome' | 'code'>('welcome')

  useEffect(() => {
    api
      .getAuthConfig()
      .then((cfg) => {
        setBotUsername(
          String(cfg.bot_username ?? '').trim(),
        )
        if (cfg.debug) setShowDebug(true)
      })
      .catch(() => {
        setConfigError(
          'Не удалось загрузить настройки. Проверьте, что API доступен.',
        )
      })
      .finally(() => setConfigReady(true))
  }, [])

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

  const handleTelegramClick = () => {
    if (!configReady) return
    if (!botUsername) {
      setConfigError(
        configError ||
          'Бот не настроен (telegram_bot_username в бэкенде).',
      )
      return
    }
    // Persist the "waiting for code" state in the URL BEFORE we
    // attempt to navigate. On mobile browsers and when popups are
    // blocked, `window.open(_, '_blank')` can navigate the current
    // tab to `t.me/<bot>` instead of opening a new one — and on
    // return / reload we'd land back on the choose screen without
    // any way to reach the code-entry form. With `?auth=code` in
    // the URL, AuthScreen re-initializes directly on TelegramAuth
    // with step='code'.
    try {
      const params = new URLSearchParams(
        window.location.search,
      )
      params.set('auth', 'code')
      const newSearch = params.toString()
      const newUrl =
        window.location.pathname +
        (newSearch ? `?${newSearch}` : '') +
        window.location.hash
      window.history.replaceState({}, '', newUrl)
    } catch {
      /* ignore */
    }
    // Switch React state first so the user sees the code-entry UI
    // even if the new tab fails to open / steals focus.
    setTelegramStartStep('code')
    setMethod('telegram')
    // Open the bot synchronously inside the click handler so the
    // browser keeps user-activation for window.open. Doing this in
    // TelegramAuth (after a state transition) is what forced the
    // second click users were seeing.
    const url = `https://t.me/${botUsername}?start=web_login`
    const opened = window.open(
      url,
      '_blank',
      'noopener,noreferrer',
    )
    setPopupBlocked(!opened)
  }

  if (method === 'telegram') {
    return (
      <TelegramAuth
        onAuth={onAuth}
        onEmail={() => setMethod('email')}
        initialStep={telegramStartStep}
        initialPopupBlocked={popupBlocked}
        botUsername={botUsername}
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
    <div className="auth-screen rb-auth-screen">
      <AmbientStage
        coverUrl={null}
        className="rb-auth__stage"
      >
        <KenBurnsCover
          src={AUTH_KB_SRC}
          alt=""
          duration={22}
          className="rb-auth__kb"
        />
      </AmbientStage>
      <div className="auth-card rb-auth__card glass--strong">
        <div className="auth-logo">{brandLabel}</div>
        <h2 className="auth-title">
          {t('auth.welcome')}
        </h2>
        <p className="auth-hint">
          {t('auth.tagline')}
          <br />
          {t('auth.subtitle')}
        </p>
        <MotionPress
          variant="primary"
          className="btn-primary auth-tg-btn"
          haptic="medium"
          onClick={handleTelegramClick}
          disabled={!configReady}
        >
          {!configReady
            ? t('common.loading', 'Загрузка…')
            : t('auth.loginTelegram')}
        </MotionPress>
        {configError && (
          <p
            className="auth-error"
            style={{
              marginTop: 8,
              fontSize: 12,
              color: '#e55',
            }}
          >
            {configError}
          </p>
        )}
        <p className="auth-microcopy">
          {t('auth.tgMicrocopy')}
        </p>
        <MotionPress
          variant="ghost"
          className="btn-secondary auth-back"
          haptic="light"
          onClick={() => setMethod('email')}
        >
          {t('auth.loginEmail')}
        </MotionPress>
        <p className="auth-microcopy auth-microcopy--muted">
          Продолжая, вы принимаете{' '}
          <a
            href={`${import.meta.env.BASE_URL}legal/terms`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Условия использования
          </a>
          {' и '}
          <a
            href={
              `${import.meta.env.BASE_URL}legal/privacy`
            }
            target="_blank"
            rel="noopener noreferrer"
          >
            Политику конфиденциальности
          </a>
          . Сервис 18+.
        </p>
        <p className="auth-microcopy auth-microcopy--muted">
          {t('auth.afterLogin')}
        </p>
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
