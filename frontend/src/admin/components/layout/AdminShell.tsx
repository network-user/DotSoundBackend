import {
  ReactNode,
  useEffect,
  useState,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../../lib/adminApi'
import { useAdminAuth } from '../../store/adminAuthStore'
import { AdminMenu } from './AdminMenu'

interface Props {
  children: ReactNode
}

export function AdminShell({ children }: Props) {
  const navigate = useNavigate()
  const reset = useAdminAuth((s) => s.reset)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const id = window.setInterval(() => {
      setNow(Date.now())
    }, 1000)
    return () => window.clearInterval(id)
  }, [])

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
            admin
          </span>
        </div>
        <AdminMenu />
        <div className="admin-shell__sidebar-foot">
          <Press
            variant="ghost"
            onClick={handleLogout}
          >
            Sign out
          </Press>
        </div>
      </aside>
      <div className="admin-shell__body">
        <header className="admin-shell__topbar">
          <span className="admin-shell__topbar-title">
            Admin Panel
          </span>
          <span className="admin-shell__topbar-time">
            {new Date(now).toLocaleTimeString()}
          </span>
        </header>
        <main className="admin-shell__main">
          {children}
        </main>
      </div>
    </div>
  )
}
