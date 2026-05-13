import {
  useCallback,
  useEffect,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '@/lib/i18n'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  AdminApiError,
  adminApi,
} from '../../lib/adminApi'
import {
  getFlowEpoch,
  getLastAutoSentFlowEpoch,
  markAutoApprovalSentForCurrentFlow,
} from '../../lib/adminDeviceApprovalSession'
import { useAdminAuth } from '../../store/adminAuthStore'
import { TotpInput } from './TotpInput'

let startedAutoApprovalForFlowEpoch = ''

export function DeviceApproval() {
  const { t } = useTranslation()
  const pendingDeviceId = useAdminAuth(
    (s) => s.pendingDeviceId,
  )
  const setSession = useAdminAuth((s) => s.setSession)
  const [emailCode, setEmailCode] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [label, setLabel] = useState('')
  const [busy, setBusy] = useState(false)
  const [approvalBusy, setApprovalBusy] =
    useState(false)
  const [error, setError] = useState<string | null>(
    null,
  )

  const sendApprovalRequest = useCallback(
    async (force: boolean): Promise<boolean> => {
      if (!pendingDeviceId) return false
      setApprovalBusy(true)
      setError(null)
      try {
        await adminApi.requestDeviceApproval(
          pendingDeviceId,
          force ? { force: true } : undefined,
        )
        return true
      } catch (err) {
        let message: string
        if (
          err instanceof AdminApiError &&
          err.status === 429
        ) {
          message = i18n.t('admin.auth.rateLimited')
        } else if (err instanceof Error) {
          message = err.message
        } else {
          message = String(err)
        }
        setError(message)
        return false
      } finally {
        setApprovalBusy(false)
      }
    },
    [pendingDeviceId],
  )

  useEffect(() => {
    if (!pendingDeviceId) return
    const flow = getFlowEpoch()
    const lastSent = getLastAutoSentFlowEpoch()
    if (flow && lastSent === flow) {
      return
    }
    if (flow && startedAutoApprovalForFlowEpoch === flow) {
      return
    }
    if (flow) {
      startedAutoApprovalForFlowEpoch = flow
    }
    void (async () => {
      const ok = await sendApprovalRequest(false)
      if (ok) {
        markAutoApprovalSentForCurrentFlow()
      }
    })()
  }, [pendingDeviceId, sendApprovalRequest])

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
      let message: string
      if (
        err instanceof AdminApiError &&
        err.status === 429
      ) {
        message = i18n.t('admin.auth.rateLimited')
      } else if (err instanceof Error) {
        message = err.message
      } else {
        message = String(err)
      }
      setError(message)
    } finally {
      setBusy(false)
    }
  }

  function handleResend() {
    void sendApprovalRequest(true)
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
          <div className="admin-auth-error-actions">
            <MotionPress
              type="button"
              variant="ghost"
              disabled={approvalBusy}
              onClick={handleResend}
            >
              {t('admin.device.resendApproval')}
            </MotionPress>
          </div>
        </div>
      )}
      <MotionPress
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
      </MotionPress>
    </div>
  )
}
