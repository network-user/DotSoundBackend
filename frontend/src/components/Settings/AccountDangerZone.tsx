import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { MotionPress } from '@/components/ui/MotionPress'

type Status = {
  pending: boolean
  deleted_at: string | null
  grace_until: string | null
}

function formatRemaining(graceUntilIso: string): string {
  const target = new Date(graceUntilIso).getTime()
  const now = Date.now()
  const diff = Math.max(0, target - now)
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  const hours = Math.floor(
    (diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60),
  )
  if (days >= 1) return `${days}д ${hours}ч`
  const minutes = Math.floor(
    (diff % (1000 * 60 * 60)) / (1000 * 60),
  )
  return `${hours}ч ${minutes}м`
}

export function AccountDangerZone() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<Status | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const s = await api.getDeletionStatus()
        if (!cancelled) setStatus(s)
      } catch {
        if (!cancelled) setStatus(null)
      }
    }
    void load()
    const tick = setInterval(load, 60_000)
    return () => {
      cancelled = true
      clearInterval(tick)
    }
  }, [])

  const submit = async () => {
    if (text.trim() !== 'DELETE') return
    setLoading(true)
    try {
      await api.requestAccountDeletion('DELETE')
      const s = await api.getDeletionStatus()
      setStatus(s)
      setOpen(false)
      setText('')
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  const restore = async () => {
    setLoading(true)
    try {
      await api.restoreAccountAfterDeletion()
      const s = await api.getDeletionStatus()
      setStatus(s)
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  if (status?.pending && status.grace_until) {
    return (
      <div className="settings-danger-zone">
        <div className="settings-danger-zone__pending">
          <p className="twofa-hint">
            {t(
              'settings.deletionPending',
              'Аккаунт будет удалён через {{remaining}}.',
              { remaining: formatRemaining(status.grace_until) },
            )}
          </p>
          <div className="settings-danger-zone__actions">
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary"
              disabled={loading}
              onClick={() => void restore()}
            >
              {loading
                ? '…'
                : t(
                    'settings.deletionRestore',
                    'Отменить удаление',
                  )}
            </MotionPress>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="settings-danger-zone">
      {!open ? (
        <MotionPress
          type="button"
          variant="ghost"
          haptic="medium"
          className="settings-item settings-item--danger"
          onClick={() => setOpen(true)}
        >
          {t('settings.deleteAccount', 'Удалить аккаунт…')}
        </MotionPress>
      ) : (
        <div className="settings-danger-zone__form">
          <p className="twofa-hint">
            {t(
              'settings.deleteAccountConfirmHint',
              'Введите DELETE для подтверждения удаления аккаунта.',
            )}
          </p>
          <p className="twofa-hint">
            {t(
              'settings.deleteAccountGraceHint',
              'Аккаунт можно восстановить в течение grace-периода.',
            )}
          </p>
          <input
            className="form-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="DELETE"
            autoComplete="off"
          />
          <div className="settings-danger-zone__actions">
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary"
              disabled={loading || text.trim() !== 'DELETE'}
              onClick={() => void submit()}
            >
              {loading
                ? '…'
                : t(
                    'settings.deleteAccountConfirm',
                    'Подтвердить',
                  )}
            </MotionPress>
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="btn-secondary"
              disabled={loading}
              onClick={() => {
                setOpen(false)
                setText('')
              }}
            >
              {t('common.cancel', 'Отмена')}
            </MotionPress>
          </div>
        </div>
      )}
    </div>
  )
}
