import {
  useCallback,
  useEffect,
  useRef,
} from 'react'
import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useBrandLabel } from '@/lib/brand'
import { MotionPress } from '@/components/ui/MotionPress'
import { AdminMenu } from './AdminMenu'

export function AdminNavDrawer({
  open,
  onClose,
  onLogout,
}: {
  open: boolean
  onClose: () => void
  onLogout: () => void | Promise<void>
}) {
  const { t } = useTranslation()
  const brandLabel = useBrandLabel()
  const { pathname } = useLocation()
  const pathRef = useRef<string | null>(null)

  useEffect(() => {
    if (pathRef.current === null) {
      pathRef.current = pathname
      return
    }
    if (pathRef.current !== pathname) {
      pathRef.current = pathname
      onClose()
    }
  }, [pathname, onClose])

  const onKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) onClose()
    },
    [open, onClose],
  )
  useEffect(() => {
    if (!open) return
    window.addEventListener('keydown', onKey)
    return () =>
      window.removeEventListener('keydown', onKey)
  }, [open, onKey])

  if (!open) return null

  return (
    <div
      className="admin-nav-drawer-backdrop"
      role="presentation"
      onClick={onClose}
    >
      <div
        className="admin-nav-drawer"
        role="dialog"
        aria-label={t('admin.shell.brandTag')}
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="admin-nav-drawer__brand">
          {`${brandLabel} `}
          <span className="admin-shell__brand-tag">
            {t('admin.shell.brandTag')}
          </span>
        </div>
        <AdminMenu
          onNavigate={() => {
            onClose()
          }}
        />
        <div className="admin-nav-drawer__foot adm-r-nav-drawer-foot">
          <MotionPress
            variant="ghost"
            onClick={() => {
              void onLogout()
            }}
          >
            {t('admin.shell.signOut')}
          </MotionPress>
        </div>
      </div>
    </div>
  )
}
