import { useState } from 'react'
import { api } from '@/lib/api'
import { setInternalUserId } from '@/lib/telegram'

type Step = 'input' | 'code' | 'success' | 'error'

interface Props {
  onAuth: () => void
}

export function TelegramAuth({ onAuth }: Props) {
  const [step, setStep] = useState<Step>('input')
  const [telegramId, setTelegramId] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleRequestCode = async () => {
    const id = parseInt(telegramId.trim(), 10)
    if (!id || isNaN(id)) {
      setError('Введите ваш Telegram ID (число)')
      return
    }
    setLoading(true)
    setError('')
    try {
      await api.requestTelegramCode(id)
      setStep('code')
    } catch {
      setError(
        'Не удалось отправить код. '
        + 'Убедитесь что вы начали диалог с ботом.',
      )
    } finally {
      setLoading(false)
    }
  }

  const handleVerifyCode = async () => {
    const id = parseInt(telegramId.trim(), 10)
    if (!code.trim()) {
      setError('Введите код')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await api.verifyTelegramCode(
        id,
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

        {step === 'input' && (
          <>
            <h2 className="auth-title">
              Вход через Telegram
            </h2>
            <p className="auth-hint">
              Введите ваш Telegram ID. Его можно
              узнать у @userinfobot
            </p>
            <input
              className="form-input"
              type="text"
              inputMode="numeric"
              placeholder="Telegram ID"
              value={telegramId}
              onChange={(e) =>
                setTelegramId(e.target.value)
              }
              onKeyDown={(e) =>
                e.key === 'Enter' &&
                handleRequestCode()
              }
            />
            {error && (
              <div className="form-error">
                {error}
              </div>
            )}
            <button
              className="btn-primary"
              onClick={handleRequestCode}
              disabled={loading}
            >
              {loading
                ? 'Отправка...'
                : 'Получить код'}
            </button>
          </>
        )}

        {step === 'code' && (
          <>
            <h2 className="auth-title">
              Введите код
            </h2>
            <p className="auth-hint">
              Код отправлен в Telegram. Проверьте
              сообщения от бота .sound
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
                  e.target.value.replace(/\D/g, ''),
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
                setStep('input')
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
