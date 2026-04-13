import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'

type LinkStep =
  | 'idle'
  | 'email_input'
  | 'email_sent'
  | 'telegram_link'

export function LinkedAccounts() {
  const [telegramLinked, setTelegramLinked] =
    useState(false)
  const [emailLinked, setEmailLinked] =
    useState(false)
  const [email, setEmail] = useState<
    string | null
  >(null)
  const [tgUsername, setTgUsername] = useState<
    string | null
  >(null)
  const [step, setStep] =
    useState<LinkStep>('idle')
  const [emailInput, setEmailInput] = useState('')
  const [deepLink, setDeepLink] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api
      .getLinkStatus()
      .then((s) => {
        setTelegramLinked(s.telegram_linked)
        setEmailLinked(s.email_linked)
        setEmail(s.email)
        setTgUsername(s.telegram_username)
      })
      .catch(() => {})
  }, [])

  const handleLinkEmail = async () => {
    if (
      !emailInput.trim() ||
      !emailInput.includes('@')
    ) {
      setError('Введите корректный email')
      return
    }
    setLoading(true)
    setError('')
    try {
      await api.requestLinkEmail(
        emailInput.trim(),
      )
      setStep('email_sent')
    } catch (e: any) {
      const detail = e?.message || ''
      if (detail.includes('409')) {
        setError(
          'Этот email привязан к другому аккаунту',
        )
      } else {
        setError(
          'Не удалось отправить ссылку',
        )
      }
    } finally {
      setLoading(false)
    }
  }

  const handleLinkTelegram = async () => {
    setLoading(true)
    setError('')
    try {
      const res =
        await api.generateLinkTelegramCode()
      setDeepLink(res.deep_link)
      setStep('telegram_link')
    } catch {
      setError(
        'Не удалось создать ссылку',
      )
    } finally {
      setLoading(false)
    }
  }

  if (step === 'email_input') {
    return (
      <div className="linked-accounts-form">
        <h4 className="twofa-title">
          Привязать email
        </h4>
        <input
          className="form-input"
          type="email"
          placeholder="your@email.com"
          value={emailInput}
          onChange={(e) =>
            setEmailInput(e.target.value)
          }
          onKeyDown={(e) =>
            e.key === 'Enter' && handleLinkEmail()
          }
          autoFocus
        />
        {error && (
          <div className="form-error">{error}</div>
        )}
        <button
          className="btn-primary"
          onClick={handleLinkEmail}
          disabled={loading}
        >
          {loading
            ? 'Отправка...'
            : 'Отправить ссылку'}
        </button>
        <button
          className="btn-secondary"
          onClick={() => {
            setStep('idle')
            setError('')
          }}
        >
          Отмена
        </button>
      </div>
    )
  }

  if (step === 'email_sent') {
    return (
      <div className="linked-accounts-form">
        <h4 className="twofa-title">
          Проверьте почту
        </h4>
        <p className="twofa-hint">
          Ссылка для привязки отправлена на{' '}
          <strong>{emailInput}</strong>
        </p>
        <button
          className="btn-secondary"
          onClick={() => setStep('idle')}
        >
          Готово
        </button>
      </div>
    )
  }

  if (step === 'telegram_link') {
    return (
      <div className="linked-accounts-form">
        <h4 className="twofa-title">
          Привязать Telegram
        </h4>
        <p className="twofa-hint">
          Перейдите по ссылке и нажмите Start
          в боте
        </p>
        <a
          href={deepLink}
          target="_blank"
          rel="noreferrer"
          className="btn-primary"
          style={{ textAlign: 'center' }}
        >
          Открыть бота
        </a>
        <button
          className="btn-secondary"
          onClick={() => setStep('idle')}
        >
          Готово
        </button>
      </div>
    )
  }

  return (
    <>
      <div className="settings-item">
        <Icon name="send" size={20} />
        <span>
          Telegram
          {telegramLinked
            ? tgUsername
              ? ` (@${tgUsername})`
              : ' (привязан)'
            : ''}
        </span>
        {telegramLinked ? (
          <span className="settings-badge">
            привязан
          </span>
        ) : (
          <button
            className="settings-badge"
            onClick={handleLinkTelegram}
            style={{
              cursor: 'pointer',
              background: 'var(--surface-2)',
            }}
          >
            привязать
          </button>
        )}
      </div>

      <div className="settings-item">
        <Icon name="link" size={20} />
        <span>
          Email
          {emailLinked && email
            ? ` (${email})`
            : ''}
        </span>
        {emailLinked ? (
          <span className="settings-badge">
            привязан
          </span>
        ) : (
          <button
            className="settings-badge"
            onClick={() =>
              setStep('email_input')
            }
            style={{
              cursor: 'pointer',
              background: 'var(--surface-2)',
            }}
          >
            привязать
          </button>
        )}
      </div>
      {error && (
        <div className="form-error">{error}</div>
      )}
    </>
  )
}
