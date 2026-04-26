import { useMemo } from 'react'
import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAdminMenu } from '@/components/Admin/AdminContext'

export function useAdminSectionLabel(): string {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const items = useAdminMenu()
  return useMemo(() => {
    if (!items.length) {
      return t('admin.shell.title')
    }
    const exact = items.find(
      (i) => i.route === pathname,
    )
    if (exact) return exact.label
    const nonRoot = items
      .filter((i) => i.route !== '/admin')
      .sort(
        (a, b) => b.route.length - a.route.length,
      )
    const prefix = nonRoot.find(
      (i) =>
        pathname === i.route ||
        pathname.startsWith(`${i.route}/`),
    )
    if (prefix) return prefix.label
    const dash = items.find(
      (i) => i.id === 'dashboard',
    )
    if (
      pathname === '/admin' ||
      pathname === '/admin/'
    ) {
      return dash?.label ?? t('admin.shell.title')
    }
    return t('admin.shell.title')
  }, [items, pathname, t])
}
