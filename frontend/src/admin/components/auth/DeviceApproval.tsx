import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../../lib/adminApi'
import { useAdminAuth } from '../../store/adminAuthStore'
import { TotpInput } from './TotpInput'

export function DeviceApproval() {
  const { t } = useTranslation()
  const { pendingDeviceId, setSession } =
    useAdminAuth((s) => ({
      pendingDeviceId: s.pendingDeviceId,
      setSession: s.setSession,
    }))
  const [emailCode, setEmailCode] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [label, setLabel] = useState('')
  const [requested, setRequested] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(
    null,
  )

  useEffect(() => {
    if (!pendingDeviceId || requested) return
    let alive = true
    adminApi
      .requestDeviceApproval(pendingDeviceId)
      .then(() => {
        if (!alive) return
        setRequested(true)
      })
      .catch((err) => {
        if (!alive) return
        setError(err.message || 'failed')
      })
    return () => {
      alive = false
    }
  }, [pendingDeviceId, requested])

  async function handleConfirm() {
    if (
      !pendingDeviceId ||
      emailCode.length < 4 ||
      totpCode.length < 6
    ) {
      return
    }
    setBusy(true)
    setError(null)
    try {
      const result = await adminApi.confirmDevice({
        device_id: pendingDeviceId,
        email_code: emailCode.trim(),
        totp_code: totpCode,
        label: label.trim() || null,
      })
      if (result.session) {
        setSession(
          result.session.access_token,
          result.session.expires_in,
        )
      }
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : String(err)
      setError(message)
    } finally {
      setBusy(false)
    }
  }

  if (!pendingDeviceId) {
    return (
      <div className="admin-auth-card">
        <h2>{t('admin.device.title')}</h2>
        <p className="admin-auth-hint">
          {t('admin.device.noPending')}
        </p>
      </div>
    )
  }

  return (
    <div className="admin-auth-card">
      <h2>{t('admin.device.title')}</h2>
      <p className="admin-auth-hint">
        {t('admin.device.hint')}
      </p>
      <label className="admin-auth-label">
        {t('admin.device.emailCode')}
        <input
          type="text"
          inputMode="numeric"
          value={emailCode}
          onChange={(e) =>
            setEmailCode(
              e.target.value
                .replace(/\D/g, '')
                .slice(0, 8),
            )
          }
          maxLength={8}
        />
      </label>
      <label className="admin-auth-label">
        {t('admin.device.totpLabel')}
      </label>
      <TotpInput
        value={totpCode}
        onChange={setTotpCode}
        disabled={busy}
      />
      <label className="admin-auth-label">
        {t('admin.device.deviceLabel')}
        <input
          type="text"
          value={label}
          onChange={(e) =>
            setLabel(e.target.value)
          }
          placeholder={t(
            'admin.device.deviceLabelPlaceholder',
          )}
          maxLength={64}
        />
      </label>
      {error && (
        <div className="admin-auth-error">
          {error}
        </div>
      )}
      <Press
        variant="primary"
        onClick={handleConfirm}
        disabled={
          busy ||
          emailCode.length < 4 ||
          totpCode.length < 6
        }
      >
        {busy
          ? t('admin.device.approving')
          : t('admin.device.approve')}
      </Press>
    </div>
  )
}
