import { useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import { setInternalUserId } from '@/lib/telegram'
import { connectWS } from '@/lib/ws'

type Step = 'welcome' | 'code' | 'success'

interface Props {
  onAuth: () => void
  onEmail?: () => void
}

export function TelegramAuth({
  onAuth,
  onEmail,
}: Props) {
  const successTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const params = new URLSearchParams(
    window.location.search,
  )
  const startOnCode = params.get('auth') === 'code'

  const [step, setStep] = useState<Step>(
    startOnCode ? 'code' : 'welcome',
  )
  const [botUsername, setBotUsername] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api
      .getAuthConfig()
      .then((cfg) =>
        setBotUsername(cfg.bot_username),
      )
      .catch(() => {})
    return () => {
      if (successTimer.current)
        clearTimeout(successTimer.current)
    }
  }, [])

  const handleOpenBot = () => {
    if (!botUsername) {
      setError('Бот не настроен')
      return
    }
    window.open(
      `https://t.me/${botUsername}?start=web_login`,
      '_blank',
    )
    setStep('code')
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
      successTimer.current = setTimeout(onAuth, 1500)
    } catch {
      setError('Неверный или просроченный код')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-logo">.sound</div>

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
            <button
              className="btn-primary auth-tg-btn"
              onClick={handleOpenBot}
            >
              Войти через Telegram
            </button>
            {onEmail && (
              <button
                className="btn-secondary auth-back"
                onClick={onEmail}
              >
                Войти по email
              </button>
            )}
          </>
        )}

        {step === 'code' && (
          <>
            <h2 className="auth-title">
              Введите код
            </h2>
            <p className="auth-hint">
              Откройте бота .sound в Telegram
              <br />и введите полученный код
            </p>
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
            <button
              className="btn-primary"
              onClick={handleVerifyCode}
              disabled={loading}
            >
              {loading ? 'Проверка...' : 'Войти'}
            </button>
            <button
              className="btn-secondary auth-back"
              onClick={() => {
                setStep('welcome')
                setCode('')
                setError('')
              }}
            >
              Назад
            </button>
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
              Добро пожаловать в .sound
            </p>
          </>
        )}
      </div>
    </div>
  )
}
