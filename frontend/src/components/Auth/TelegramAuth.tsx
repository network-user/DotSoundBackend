import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { setInternalUserId } from '@/lib/telegram'
import { connectWS } from '@/lib/ws'
import { useBrandLabel } from '@/lib/brand'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  dismissIsland,
  showIsland,
} from '@/lib/island'

const AUTH_KB_SRC =
  'data:image/svg+xml,' +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24'>" +
      "<rect width='24' height='24' fill='%23242424'/></svg>",
  )

type Step = 'welcome' | 'code' | 'success'

interface Props {
  onAuth: () => void
  onEmail?: () => void
  initialStep?: 'welcome' | 'code'
  initialPopupBlocked?: boolean
  botUsername?: string
}

export function TelegramAuth({
  onAuth,
  onEmail,
  initialStep,
  initialPopupBlocked,
  botUsername: botUsernameProp,
}: Props) {
  const { t } = useTranslation()
  const brandLabel = useBrandLabel()
  const progressRef = useRef<string | null>(null)
  const successTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const params = new URLSearchParams(
    window.location.search,
  )
  const startOnCode = params.get('auth') === 'code'

  const [step, setStep] = useState<Step>(
    initialStep ?? (startOnCode ? 'code' : 'welcome'),
  )
  const [botUsername, setBotUsername] = useState(
    botUsernameProp ?? '',
  )
  const [configReady, setConfigReady] = useState(
    Boolean(botUsernameProp),
  )
  const [configFailed, setConfigFailed] = useState(false)
  const [popupBlocked, setPopupBlocked] = useState(
    Boolean(initialPopupBlocked),
  )
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!loading) {
      if (progressRef.current) {
        dismissIsland(progressRef.current)
        progressRef.current = null
      }
      return
    }
    const id = showIsland({
      kind: 'progress',
      title: t(
        'redesign.nav.authWorking',
        'Signing in…',
      ),
    })
    progressRef.current = id
    return () => {
      dismissIsland(id)
      if (progressRef.current === id) {
        progressRef.current = null
      }
    }
  }, [loading, t])

  useEffect(() => {
    if (!botUsernameProp) {
      api
        .getAuthConfig()
        .then((cfg) => {
          setBotUsername(
            String(cfg.bot_username ?? '').trim(),
          )
          setConfigFailed(false)
        })
        .catch(() => {
          setConfigFailed(true)
        })
        .finally(() => setConfigReady(true))
    }
    return () => {
      if (successTimer.current)
        clearTimeout(successTimer.current)
    }
  }, [botUsernameProp])

  const botOpenUrl =
    botUsername.length > 0
      ? `https://t.me/${botUsername}?start=web_login`
      : ''

  const handleOpenBot = () => {
    if (!configReady) {
      return
    }
    if (!botUsername) {
      setError(
        configFailed
          ? 'Не удалось загрузить настройки. Проверьте, что API доступен.'
          : 'Бот не настроен (telegram_bot_username в бэкенде).',
      )
      return
    }
    // Persist `?auth=code` in the URL so a reload / back-navigation
    // (e.g. after a mobile browser routed `t.me/<bot>` through the
    // current tab) restores the code-entry step instead of bouncing
    // the user back to the welcome screen.
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
    setStep('code')
    const url = botOpenUrl
    const opened = window.open(
      url,
      '_blank',
      'noopener,noreferrer',
    )
    setPopupBlocked(!opened)
  }

  const handleVerifyCode = async () => {
    const digits = code.replace(/\s/g, '')
    if (!digits || digits.length !== 6) {
      setError('Введите 6-значный код')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await api.verifyTelegramCode(
        digits,
      )
      setInternalUserId(res.user_id)
      if (res.access_token) {
        try {
          connectWS(res.access_token)
        } catch {
          /* ignore */
        }
        try {
          window.dispatchEvent(
            new Event('app-auth-ready'),
          )
        } catch {
          /* ignore */
        }
      }
      setStep('success')
      try {
        const params = new URLSearchParams(
          window.location.search,
        )
        if (params.get('auth') === 'code') {
          params.delete('auth')
          const newSearch = params.toString()
          const newUrl =
            window.location.pathname +
            (newSearch ? `?${newSearch}` : '') +
            window.location.hash
          window.history.replaceState({}, '', newUrl)
        }
      } catch {
        /* ignore */
      }
      successTimer.current = setTimeout(onAuth, 1500)
    } catch {
      setError('Неверный или просроченный код')
    } finally {
      setLoading(false)
    }
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

        {step === 'welcome' && (
          <>
            <h2 className="auth-title">
              Добро пожаловать
            </h2>
            <p className="auth-hint">
              Музыка без рекламы.
              <br />
              Слушай. Делись. Открывай.
            </p>
            {error && (
              <div className="form-error">
                {error}
              </div>
            )}
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary auth-tg-btn"
              onClick={handleOpenBot}
              disabled={!configReady}
            >
              {!configReady
                ? 'Загрузка…'
                : 'Войти через Telegram'}
            </MotionPress>
            {configReady &&
              botUsername.length > 0 &&
              botOpenUrl.length > 0 && (
                <a
                  className="auth-link"
                  href={botOpenUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Открыть бота в новой вкладке
                </a>
              )}
            {onEmail && (
              <MotionPress
                type="button"
                variant="ghost"
                haptic="light"
                className="btn-secondary auth-back"
                onClick={onEmail}
              >
                Войти по email
              </MotionPress>
            )}
          </>
        )}

        {step === 'code' && (
          <>
            <h2 className="auth-title">
              Введите код
            </h2>
            <p className="auth-hint">
              Откройте бота {brandLabel} в Telegram
              <br />и введите полученный код
            </p>
            {popupBlocked &&
              botOpenUrl.length > 0 && (
                <p className="auth-hint">
                  Вкладка могла быть заблокирована.
                  <br />
                  <a
                    className="auth-link"
                    href={botOpenUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Открыть бота вручную
                  </a>
                </p>
              )}
            <input
              className="form-input auth-code-input"
              type="text"
              inputMode="numeric"
              maxLength={7}
              placeholder="000 000"
              value={code}
              onChange={(e) =>
                setCode(
                  e.target.value.replace(
                    /[^\d ]/g,
                    '',
                  ),
                )
              }
              onKeyDown={(e) =>
                e.key === 'Enter' &&
                handleVerifyCode()
              }
              autoFocus
            />
            {error && (
              <div className="form-error">
                {error}
              </div>
            )}
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary"
              onClick={handleVerifyCode}
              disabled={loading}
            >
              {loading ? 'Проверка...' : 'Войти'}
            </MotionPress>
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="btn-secondary auth-back"
              onClick={() => {
                setStep('welcome')
                setCode('')
                setError('')
                setPopupBlocked(false)
                try {
                  const params = new URLSearchParams(
                    window.location.search,
                  )
                  if (params.get('auth') === 'code') {
                    params.delete('auth')
                    const newSearch = params.toString()
                    const newUrl =
                      window.location.pathname +
                      (newSearch ? `?${newSearch}` : '') +
                      window.location.hash
                    window.history.replaceState(
                      {},
                      '',
                      newUrl,
                    )
                  }
                } catch {
                  /* ignore */
                }
              }}
            >
              Назад
            </MotionPress>
          </>
        )}

        {step === 'success' && (
          <>
            <div className="auth-success-icon">
              ✓
            </div>
            <h2 className="auth-title">
              Вход выполнен
            </h2>
            <p className="auth-hint">
              Добро пожаловать в {brandLabel}
            </p>
          </>
        )}
      </div>
    </div>
  )
}
