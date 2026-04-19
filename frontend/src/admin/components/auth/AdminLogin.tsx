import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../../lib/adminApi'
import { computeFingerprint } from '../../lib/fingerprint'
import { useAdminAuth } from '../../store/adminAuthStore'
import { TotpInput } from './TotpInput'

export function AdminLogin() {
  const { t } = useTranslation()
  const setSession = useAdminAuth(
    (s) => s.setSession,
  )
  const setPendingDevice = useAdminAuth(
    (s) => s.setPendingDevice,
  )
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(
    null,
  )

  async function handleSubmit() {
    if (code.length < 6) return
    setBusy(true)
    setError(null)
    try {
      const fingerprint =
        await computeFingerprint()
      const result = await adminApi.login({
        code,
        fingerprint,
      })
      if (result.requires_device_approval) {
        if (result.device_id) {
          setPendingDevice(result.device_id)
        } else {
          setError('device approval required')
        }
        return
      }
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

  return (
    <div className="admin-auth-card">
      <h2>{t('admin.auth.signInTitle')}</h2>
      <p className="admin-auth-hint">
        {t('admin.auth.signInHint')}
      </p>
      <TotpInput
        value={code}
        onChange={setCode}
        onComplete={handleSubmit}
        autoFocus
        disabled={busy}
      />
      {error && (
        <div className="admin-auth-error">
          {error}
        </div>
      )}
      <Press
        variant="primary"
        onClick={handleSubmit}
        disabled={busy || code.length < 6}
      >
        {busy
          ? t('admin.auth.signingIn')
          : t('admin.auth.signIn')}
      </Press>
    </div>
  )
}
