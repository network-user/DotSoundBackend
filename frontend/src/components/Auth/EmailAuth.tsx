import { useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import { setInternalUserId } from '@/lib/telegram'
import { connectWS } from '@/lib/ws'

function notifyAuthReady(token: string | null): void {
  if (token) {
    try {
      connectWS(token)
    } catch {
      /* ignore */
    }
  }
  try {
    window.dispatchEvent(
      new Event('app-auth-ready'),
    )
  } catch {
    /* ignore */
  }
}

type Step =
  | 'email'
  | 'check_inbox'
  | 'totp'
  | 'success'

interface Props {
  onAuth: () => void
  onBack: () => void
}

export function EmailAuth({
  onAuth,
  onBack,
}: Props) {
  const successTimer = useRef<ReturnType<
    typeof setTimeout
  > | null>(null)
  const [step, setStep] =
    useState<Step>('email')
  const [email, setEmail] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [sessionToken, setSessionToken] =
    useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [
    fallbackMode,
    setFallbackMode,
  ] = useState(false)
  const [fallbackSent, setFallbackSent] =
    useState(false)

  useEffect(() => {
    const params = new URLSearchParams(
      window.location.search,
    )
    const token = params.get('token')
    if (token) {
      window.history.replaceState(
        {},
        '',
        window.location.pathname,
      )
      handleVerifyToken(token)
    }
    return () => {
      if (successTimer.current)
        clearTimeout(successTimer.current)
    }
  }, [])

  const handleRequestLink = async () => {
    if (!email.trim() || !email.includes('@')) {
      setError('Введите корректный email')
      return
    }
    setLoading(true)
    setError('')
    try {
      await api.requestMagicLink(email.trim())
      setStep('check_inbox')
    } catch {
      setError(
        'Не удалось отправить ссылку',
      )
    } finally {
      setLoading(false)
    }
  }

  const handleVerifyToken = async (
    token: string,
  ) => {
    setLoading(true)
    setError('')
    try {
      const res =
        await api.verifyMagicLink(token)
      if (res.requires_2fa && res.session_token) {
        setSessionToken(res.session_token)
        setStep('totp')
      } else if (res.user_id) {
        setInternalUserId(res.user_id)
        notifyAuthReady(res.access_token)
        setStep('success')
        successTimer.current = setTimeout(
          onAuth,
          1500,
        )
      }
    } catch {
      setError(
        'Ссылка недействительна или просрочена',
      )
      setStep('email')
    } finally {
      setLoading(false)
    }
  }

  const handleVerifyTotp = async () => {
    const digits = totpCode.replace(/\s/g, '')
    if (digits.length !== 6) {
      setError('Введите 6-значный код')
      return
    }
    setLoading(true)
    setError('')
    try {
      let res
      if (fallbackMode) {
        res =
          await api.verify2FAEmailFallback(
            sessionToken,
            digits,
          )
      } else {
        res = await api.verify2FA(
          sessionToken,
          digits,
        )
      }
      if (res.user_id) {
        setInternalUserId(res.user_id)
        notifyAuthReady(res.access_token)
        setStep('success')
        successTimer.current = setTimeout(
          onAuth,
          1500,
        )
      }
    } catch {
      setError('Неверный код')
    } finally {
      setLoading(false)
    }
  }

  const handleRequestFallback = async () => {
    setError('')
    try {
      await api.request2FAEmailFallback(
        sessionToken,
      )
      setFallbackMode(true)
      setFallbackSent(true)
      setTotpCode('')
    } catch {
      setError(
        'Не удалось отправить код',
      )
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-logo">.sound</div>

        {step === 'email' && (
          <>
            <h2 className="auth-title">
              Вход по email
            </h2>
            <p className="auth-hint">
              Введите email — мы отправим
              <br />
              ссылку для входа
            </p>
            <input
              className="form-input"
              type="email"
              placeholder="your@email.com"
              value={email}
              onChange={(e) =>
                setEmail(e.target.value)
              }
              onKeyDown={(e) =>
                e.key === 'Enter' &&
                handleRequestLink()
              }
              autoFocus
            />
            {error && (
              <div className="form-error">
                {error}
              </div>
            )}
            <button
              className="btn-primary auth-tg-btn"
              onClick={handleRequestLink}
              disabled={loading}
            >
              {loading
                ? 'Отправка...'
                : 'Получить ссылку'}
            </button>
            <button
              className="btn-secondary auth-back"
              onClick={onBack}
            >
              Назад
            </button>
          </>
        )}

        {step === 'check_inbox' && (
          <>
            <h2 className="auth-title">
              Проверьте почту
            </h2>
            <p className="auth-hint">
              Мы отправили ссылку на
              <br />
              <strong>{email}</strong>
              <br />
              Перейдите по ней для входа
            </p>
            <button
              className="btn-secondary auth-back"
              onClick={() => {
                setStep('email')
                setError('')
              }}
            >
              Отправить заново
            </button>
          </>
        )}

        {step === 'totp' && (
          <>
            <h2 className="auth-title">
              {fallbackMode
                ? 'Код из email'
                : 'Двухфакторная аутентификация'}
            </h2>
            <p className="auth-hint">
              {fallbackMode
                ? 'Введите код из письма'
                : 'Введите код из приложения-аутентификатора'}
            </p>
            <input
              className="form-input auth-code-input"
              type="text"
              inputMode="numeric"
              maxLength={fallbackMode ? 7 : 6}
              placeholder={
                fallbackMode
                  ? '000 000'
                  : '000000'
              }
              value={totpCode}
              onChange={(e) =>
                setTotpCode(
                  fallbackMode
                    ? e.target.value.replace(
                        /[^\d ]/g,
                        '',
                      )
                    : e.target.value.replace(
                        /\D/g,
                        '',
                      ),
                )
              }
              onKeyDown={(e) =>
                e.key === 'Enter' &&
                handleVerifyTotp()
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
              onClick={handleVerifyTotp}
              disabled={loading}
            >
              {loading
                ? 'Проверка...'
                : 'Подтвердить'}
            </button>
            {!fallbackMode && (
              <button
                className="btn-secondary auth-back"
                onClick={handleRequestFallback}
                disabled={fallbackSent}
              >
                {fallbackSent
                  ? 'Код отправлен на email'
                  : 'Получить код на email'}
              </button>
            )}
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
