import {
  ReactNode,
  useEffect,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../../lib/adminApi'
import { useAdminAuth } from '../../store/adminAuthStore'
import { AdminMenu } from './AdminMenu'

interface Props {
  children: ReactNode
}

function Clock() {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => {
      setNow(Date.now())
    }, 1000)
    return () => window.clearInterval(id)
  }, [])
  return (
    <span className="admin-shell__topbar-time">
      {new Date(now).toLocaleTimeString()}
    </span>
  )
}

export function AdminShell({ children }: Props) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const reset = useAdminAuth((s) => s.reset)

  async function handleLogout() {
    try {
      await adminApi.logout()
    } catch {
      // ignore network errors on logout
    }
    reset()
    navigate('/')
  }

  return (
    <div className="admin-shell">
      <aside className="admin-shell__sidebar">
        <div className="admin-shell__brand">
          .sound{' '}
          <span className="admin-shell__brand-tag">
            {t('admin.shell.brandTag')}
          </span>
        </div>
        <AdminMenu />
        <div className="admin-shell__sidebar-foot">
          <Press
            variant="ghost"
            onClick={handleLogout}
          >
            {t('admin.shell.signOut')}
          </Press>
        </div>
      </aside>
      <div className="admin-shell__body">
        <header className="admin-shell__topbar">
          <span className="admin-shell__topbar-title">
            {t('admin.shell.title')}
          </span>
          <Clock />
        </header>
        <main className="admin-shell__main">
          {children}
        </main>
      </div>
    </div>
  )
}
