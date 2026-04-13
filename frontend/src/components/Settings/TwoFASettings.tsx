import { useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'

type Step =
  | 'idle'
  | 'loading'
  | 'setup'
  | 'confirm'
  | 'disable'

interface Props {
  enabled: boolean
  onToggle: (enabled: boolean) => void
}

export function TwoFASettings({
  enabled,
  onToggle,
}: Props) {
  const [step, setStep] =
    useState<Step>('idle')
  const [qr, setQr] = useState('')
  const [backupCodes, setBackupCodes] = useState<
    string[]
  >([])
  const [code, setCode] = useState('')
  const [error, setError] = useState('')

  const handleSetup = async () => {
    setStep('loading')
    setError('')
    try {
      const res = await api.setup2FA()
      setQr(res.qr_code_base64)
      setBackupCodes(res.backup_codes)
      setStep('setup')
    } catch {
      setError(
        'Не удалось настроить 2FA',
      )
      setStep('idle')
    }
  }

  const handleConfirm = async () => {
    if (code.length !== 6) {
      setError('Введите 6-значный код')
      return
    }
    setError('')
    try {
      await api.confirm2FA(code)
      onToggle(true)
      setStep('idle')
      setCode('')
    } catch {
      setError('Неверный код')
    }
  }

  const handleDisable = async () => {
    if (code.length !== 6) {
      setError('Введите 6-значный код')
      return
    }
    setError('')
    try {
      await api.disable2FA(code)
      onToggle(false)
      setStep('idle')
      setCode('')
    } catch {
      setError('Неверный код')
    }
  }

  if (step === 'setup') {
    return (
      <div className="twofa-setup">
        <h3 className="twofa-title">
          Настройка 2FA
        </h3>
        <p className="twofa-hint">
          Отсканируйте QR-код в
          приложении-аутентификаторе (Google
          Authenticator, Authy)
        </p>
        {qr && (
          <img
            src={`data:image/png;base64,${qr}`}
            alt="QR"
            className="twofa-qr"
          />
        )}
        <p className="twofa-hint">
          Резервные коды (сохраните их):
        </p>
        <div className="twofa-backup-codes">
          {backupCodes.map((c) => (
            <code key={c}>{c}</code>
          ))}
        </div>
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
            e.key === 'Enter' && handleConfirm()
          }
        />
        {error && (
          <div className="form-error">{error}</div>
        )}
        <button
          className="btn-primary"
          onClick={handleConfirm}
        >
          Подтвердить
        </button>
        <button
          className="btn-secondary"
          onClick={() => {
            setStep('idle')
            setCode('')
            setError('')
          }}
        >
          Отмена
        </button>
      </div>
    )
  }

  if (step === 'disable') {
    return (
      <div className="twofa-setup">
        <h3 className="twofa-title">
          Отключение 2FA
        </h3>
        <p className="twofa-hint">
          Введите код из
          приложения-аутентификатора
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
            e.key === 'Enter' && handleDisable()
          }
        />
        {error && (
          <div className="form-error">{error}</div>
        )}
        <button
          className="btn-primary"
          onClick={handleDisable}
        >
          Отключить 2FA
        </button>
        <button
          className="btn-secondary"
          onClick={() => {
            setStep('idle')
            setCode('')
            setError('')
          }}
        >
          Отмена
        </button>
      </div>
    )
  }

  return (
    <div
      className="settings-item"
      onClick={
        enabled
          ? () => setStep('disable')
          : handleSetup
      }
    >
      <Icon name="lock" size={20} />
      <span>
        Двухфакторная аутентификация
      </span>
      {step === 'loading' ? (
        <span className="settings-badge">...</span>
      ) : (
        <div
          className={`settings-toggle${enabled ? ' on' : ''}`}
        >
          <div className="settings-toggle-dot" />
        </div>
      )}
      {error && (
        <div className="form-error">{error}</div>
      )}
    </div>
  )
}
