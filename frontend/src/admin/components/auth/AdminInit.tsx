import {
  useEffect,
  useMemo,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import QRCode from 'qrcode'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../../lib/adminApi'
import { computeFingerprint } from '../../lib/fingerprint'
import { useAdminAuth } from '../../store/adminAuthStore'
import { TotpInput } from './TotpInput'

export function AdminInit() {
  const { t } = useTranslation()
  const setSession = useAdminAuth(
    (s) => s.setSession,
  )
  const [secret, setSecret] = useState<string | null>(
    null,
  )
  const [otpauthUri, setOtpauthUri] =
    useState<string | null>(null)
  const [qrDataUrl, setQrDataUrl] =
    useState<string | null>(null)
  const [showSecret, setShowSecret] = useState(false)
  const [code, setCode] = useState('')
  const [label, setLabel] = useState('')
  const [error, setError] = useState<string | null>(
    null,
  )
  const [busy, setBusy] = useState(false)
  const [backupCodes, setBackupCodes] = useState<
    string[] | null
  >(null)

  useEffect(() => {
    let alive = true
    adminApi
      .initStart()
      .then((data) => {
        if (!alive) return
        setSecret(data.secret_b32)
        setOtpauthUri(data.otpauth_uri)
      })
      .catch((err) =>
        setError(err.message || 'init failed'),
      )
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    if (!otpauthUri) return
    QRCode.toDataURL(otpauthUri, {
      margin: 2,
      width: 240,
    })
      .then((url) => setQrDataUrl(url))
      .catch(() => setQrDataUrl(null))
  }, [otpauthUri])

  const heading = useMemo(
    () =>
      backupCodes
        ? t('admin.init.backupCodes')
        : t('admin.init.title'),
    [backupCodes, t],
  )

  async function handleConfirm() {
    if (!code || code.length < 6) return
    setBusy(true)
    setError(null)
    try {
      const fingerprint =
        await computeFingerprint()
      const result = await adminApi.initConfirm({
        code,
        fingerprint,
        label: label.trim() || null,
      })
      setBackupCodes(result.backup_codes)
      setSession(
        result.session.access_token,
        result.session.expires_in,
      )
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

  if (backupCodes) {
    return (
      <div className="admin-auth-card">
        <h2>{heading}</h2>
        <p className="admin-auth-hint">
          {t('admin.init.backupCodesHint')}
        </p>
        <ul className="admin-backup-codes">
          {backupCodes.map((code) => (
            <li key={code}>
              <code>{code}</code>
            </li>
          ))}
        </ul>
        <Press
          variant="primary"
          onClick={() => {
            window.location.href = '/admin'
          }}
        >
          {t('admin.init.continue')}
        </Press>
      </div>
    )
  }

  return (
    <div className="admin-auth-card">
      <h2>{heading}</h2>
      <p className="admin-auth-hint">
        {t('admin.init.hint')}
      </p>
      {qrDataUrl ? (
        <img
          className="admin-auth-qr"
          src={qrDataUrl}
          alt="TOTP QR code"
          width={240}
          height={240}
        />
      ) : (
        <div className="admin-auth-qr admin-auth-qr--placeholder" />
      )}
      <button
        type="button"
        className="admin-auth-toggle"
        onClick={() => setShowSecret((v) => !v)}
      >
        {showSecret
          ? t('admin.init.hideSecret')
          : t('admin.init.showSecret')}
      </button>
      {showSecret && secret && (
        <code className="admin-auth-secret">
          {secret}
        </code>
      )}
      <label className="admin-auth-label">
        {t('admin.init.deviceLabel')}
        <input
          type="text"
          value={label}
          onChange={(e) =>
            setLabel(e.target.value)
          }
          placeholder={t(
            'admin.init.deviceLabelPlaceholder',
          )}
          maxLength={64}
        />
      </label>
      <TotpInput
        value={code}
        onChange={setCode}
        onComplete={handleConfirm}
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
        onClick={handleConfirm}
        disabled={busy || code.length < 6}
      >
        {busy
          ? t('admin.auth.confirming')
          : t('admin.auth.confirm')}
      </Press>
    </div>
  )
}
