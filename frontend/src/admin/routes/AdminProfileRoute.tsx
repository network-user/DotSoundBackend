import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { MotionPress } from '@/components/ui/MotionPress'
import { adminApi } from '../lib/adminApi'
import { decodeAdminJwtHint } from '../lib/adminJwtHint'
import { useAdminAuth } from '../store/adminAuthStore'

function formatExpiresAt(ts: number | null): string {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return '—'
  }
}

export function AdminProfileRoute() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const reset = useAdminAuth((s) => s.reset)
  const accessToken = useAdminAuth((s) => s.accessToken)
  const expiresAt = useAdminAuth((s) => s.expiresAt)
  const capabilities = useAdminAuth((s) => s.capabilities)

  const hint = useMemo(
    () => decodeAdminJwtHint(accessToken),
    [accessToken],
  )

  async function handleLogout() {
    try {
      await adminApi.logout()
    } catch {
    }
    reset()
    navigate('/')
  }

  return (
    <div>
      <h1>{t('redesign.admin.profileTitle')}</h1>
      <section className="glass--medium admin-card adm-r-profile-card">
        <p className="admin-card__sub">
          {t('redesign.admin.profileSubtitle')}
        </p>
        {hint && (
          <p className="adm-r-profile-card__hint">{hint}</p>
        )}
        <dl className="adm-r-profile-dl">
          <dt>{t('redesign.admin.profileSessionExpires')}</dt>
          <dd>{formatExpiresAt(expiresAt)}</dd>
          <dt>{t('redesign.admin.profileCapabilities')}</dt>
          <dd>
            {capabilities.length ? (
              <ul className="adm-r-profile-caps">
                {capabilities.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            ) : (
              t('redesign.admin.profileCapsEmpty')
            )}
          </dd>
        </dl>
        <MotionPress
          variant="ghost"
          className="adm-r-profile-logout"
          onClick={() => {
            void handleLogout()
          }}
        >
          {t('admin.shell.signOut')}
        </MotionPress>
      </section>
    </div>
  )
}
