import {
  ReactNode,
  useCallback,
  useEffect,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { Press } from '@/components/ui/Press'
import { useAdminSectionLabel } from '../../hooks/useAdminSectionLabel'
import { useIsNarrowLayout } from '../../hooks/useIsNarrowLayout'
import { adminApi } from '../../lib/adminApi'
import { useAdminAuth } from '../../store/adminAuthStore'
import { AdminMenu } from './AdminMenu'
import { AdminNavDrawer } from './AdminNavDrawer'

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
  const sectionLabel = useAdminSectionLabel()
  const narrow = useIsNarrowLayout()
  const [menuOpen, setMenuOpen] = useState(false)

  const closeMenu = useCallback(
    () => setMenuOpen(false),
    [],
  )

  async function handleLogout() {
    try {
      await adminApi.logout()
    } catch {
      // ignore network errors on logout
    }
    setMenuOpen(false)
    reset()
    navigate('/')
  }

  return (
    <div
      className={
        narrow
          ? 'admin-shell admin-shell--compact'
          : 'admin-shell'
      }
    >
      {!narrow && (
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
      )}
      {narrow && (
        <AdminNavDrawer
          open={menuOpen}
          onClose={closeMenu}
          onLogout={handleLogout}
        />
      )}
      <div className="admin-shell__body">
        <header className="admin-shell__topbar">
          {narrow && (
            <Press
              variant="ghost"
              className="admin-shell__nav-toggle"
              onClick={() =>
                setMenuOpen((o) => !o)
              }
              aria-expanded={menuOpen}
              aria-label={
                menuOpen
                  ? t('admin.shell.closeMenu')
                  : t('admin.shell.openMenu')
              }
              iconOnly
            >
              <Icon
                name={menuOpen ? 'x' : 'list'}
                size={20}
              />
            </Press>
          )}
          <span
            className="admin-shell__topbar-title"
            title={t('admin.shell.title')}
          >
            {sectionLabel}
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
