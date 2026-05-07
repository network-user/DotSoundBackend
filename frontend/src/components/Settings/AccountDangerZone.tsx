import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { MotionPress } from '@/components/ui/MotionPress'

export function AccountDangerZone() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    if (text.trim() !== 'DELETE') return
    setLoading(true)
    try {
      await api.requestAccountDeletion('DELETE')
      api.logout()
      window.location.reload()
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="settings-danger-zone">
      <div className="settings-hint">
        {t(
          'settings.dangerZoneTitle',
          'Аккаунт',
        )}
      </div>
      {!open ? (
        <MotionPress
          type="button"
          variant="ghost"
          haptic="medium"
          className="settings-item settings-item--danger"
          onClick={() => setOpen(true)}
        >
          {t(
            'settings.deleteAccount',
            'Удалить аккаунт…',
          )}
        </MotionPress>
      ) : (
        <div className="settings-danger-zone__form">
          <p className="twofa-hint">
            {t(
              'settings.deleteAccountConfirmHint',
              'Введите DELETE для подтверждения удаления аккаунта.',
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
              disabled={
                loading || text.trim() !== 'DELETE'
              }
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
