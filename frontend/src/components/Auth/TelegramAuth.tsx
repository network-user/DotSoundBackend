import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { setInternalUserId } from '@/lib/telegram'

type Step = 'welcome' | 'code' | 'success'

interface Props {
  onAuth: () => void
}

export function TelegramAuth({ onAuth }: Props) {
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
    if (!code.trim() || code.length !== 6) {
      setError('Введите 6-значный код')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await api.verifyTelegramCode(
        code.trim(),
      )
      setInternalUserId(res.user_id)
      setStep('success')
      setTimeout(onAuth, 1500)
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
              maxLength={6}
              placeholder="000000"
              value={code}
              onChange={(e) =>
                setCode(
                  e.target.value.replace(
                    /\D/g,
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
