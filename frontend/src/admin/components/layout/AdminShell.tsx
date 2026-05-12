import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { AnimatePresence } from 'framer-motion'
import { useBrandLabel } from '@/lib/brand'
import {
  useNavigate,
  useLocation,
  Outlet,
} from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { getAdminPanelRoute } from '@/lib/adminPath'
import {
  m,
  SPRING_LAYOUT,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { MotionPress } from '@/components/ui/MotionPress'
import { useAdminSectionLabel } from '../../hooks/useAdminSectionLabel'
import { useIsNarrowLayout } from '../../hooks/useIsNarrowLayout'
import { useAdminTheme } from '../../hooks/useAdminTheme'
import { adminApi } from '../../lib/adminApi'
import { useAdminAuth } from '../../store/adminAuthStore'
import { decodeAdminJwtHint } from '../../lib/adminJwtHint'
import { AdminMenu } from './AdminMenu'
import { AdminNavDrawer } from './AdminNavDrawer'
import { AdminBreadcrumb } from './AdminBreadcrumb'
import { CommandPalette } from '../widgets/CommandPalette'

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

const ADMIN_PAGE_ENTER = {
  opacity: 0,
  y: 14,
} as const

const ADMIN_PAGE_ANIMATE = {
  opacity: 1,
  y: 0,
} as const

const ADMIN_PAGE_EXIT = {
  opacity: 0,
  y: -10,
} as const

export function AdminShell() {
  const { t } = useTranslation()
  const brandLabel = useBrandLabel()
  const navigate = useNavigate()
  const location = useLocation()
  const reduce = useReducedMotion()
  const reset = useAdminAuth((s) => s.reset)
  const accessToken = useAdminAuth(
    (s) => s.accessToken,
  )
  const sectionLabel = useAdminSectionLabel()
  const narrow = useIsNarrowLayout()
  const [menuOpen, setMenuOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const { theme, toggle: toggleTheme } = useAdminTheme()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const isCmdK =
        (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k'
      if (isCmdK) {
        e.preventDefault()
        setPaletteOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const jwtHint = useMemo(
    () => decodeAdminJwtHint(accessToken),
    [accessToken],
  )

  const subtitle = useMemo(() => {
    const bits = [
      jwtHint,
      sectionLabel,
    ].filter(Boolean)
    return bits.join(' · ')
  }, [jwtHint, sectionLabel])

  const closeMenu = useCallback(() => setMenuOpen(false), [])

  async function handleLogout() {
    try {
      await adminApi.logout()
    } catch {
    }
    setMenuOpen(false)
    reset()
    navigate('/')
  }

  const transition = reduce ? TWEEN_FAST : SPRING_LAYOUT

  return (
    <div
      className={
        narrow
          ? 'admin-shell admin-shell--compact'
          : 'admin-shell'
      }
      data-admin-theme={theme}
    >
      {!narrow && (
        <aside className="admin-shell__sidebar">
          <div className="admin-shell__brand">
            {brandLabel}{' '}
            <span className="admin-shell__brand-tag">
              {t('admin.shell.brandTag')}
            </span>
          </div>
          <AdminMenu />
          <div className="admin-shell__sidebar-foot">
            <MotionPress
              variant="ghost"
              className="admin-shell__profile-wide"
              onClick={() => {
                navigate(getAdminPanelRoute('/profile'))
              }}
            >
              {t('redesign.admin.profileTitle')}
            </MotionPress>
            <MotionPress
              variant="ghost"
              className="admin-shell__logout-wide"
              onClick={() => {
                void handleLogout()
              }}
            >
              {t('admin.shell.signOut')}
            </MotionPress>
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
            <MotionPress
              variant="icon"
              className="admin-shell__nav-toggle"
              onClick={() => setMenuOpen((o) => !o)}
              aria-expanded={menuOpen}
              aria-label={
                menuOpen
                  ? t('admin.shell.closeMenu')
                  : t('admin.shell.openMenu')
              }
            >
              <Icon
                name={menuOpen ? 'x' : 'list'}
                size={20}
              />
            </MotionPress>
          )}
          {narrow ? (
            <span
              className="admin-shell__topbar-title"
              title={t('admin.shell.title')}
            >
              {sectionLabel}
            </span>
          ) : (
            <AdminBreadcrumb />
          )}
          <button
            type="button"
            className="admin-shell__cmdk-btn"
            onClick={() => setPaletteOpen(true)}
            aria-label={t('admin.cmdk.open', 'Open command palette')}
          >
            <Icon name="search" size={12} />
            <span>
              {t('admin.cmdk.trigger', 'Search')}
            </span>
            <kbd>⌘K</kbd>
          </button>
          <button
            type="button"
            className="admin-theme-toggle"
            onClick={toggleTheme}
            aria-label={
              theme === 'dark'
                ? t('admin.theme.toLight', 'Switch to light theme')
                : t('admin.theme.toDark', 'Switch to dark theme')
            }
            title={
              theme === 'dark'
                ? t('admin.theme.toLight', 'Switch to light theme')
                : t('admin.theme.toDark', 'Switch to dark theme')
            }
          >
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={14} />
          </button>
          <Clock />
        </header>
        {!narrow && (
          <div className="adm-r-page-head">
            <h1 className="adm-r-page-head__title">
              {t('redesign.admin.pageTitle')}
            </h1>
            <p className="adm-r-page-head__sub">
              {subtitle}
            </p>
          </div>
        )}
        <main className="admin-shell__main adm-r-main-inner">
          <AnimatePresence mode="wait">
            <m.div
              key={location.pathname}
              initial={
                reduce ? false : ADMIN_PAGE_ENTER
              }
              animate={ADMIN_PAGE_ANIMATE}
              exit={reduce ? undefined : ADMIN_PAGE_EXIT}
              transition={transition}
            >
              <Outlet />
            </m.div>
          </AnimatePresence>
        </main>
      </div>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
      />
    </div>
  )
}
