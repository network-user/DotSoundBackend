import { useMemo } from 'react'
import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAdminMenu } from '@/components/Admin/AdminContext'
import { getAdminPanelRoute } from '@/lib/adminPath'

export function useAdminSectionLabel(): string {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const items = useAdminMenu()
  return useMemo(() => {
    const root = getAdminPanelRoute()
    const profile = getAdminPanelRoute('/profile')
    if (
      pathname === profile ||
      pathname.endsWith(profile)
    ) {
      return t('redesign.admin.profileTitle')
    }
    if (!items.length) {
      return t('admin.shell.title')
    }
    const exact = items.find(
      (i) => i.route === pathname,
    )
    if (exact) return exact.label
    const nonRoot = items
      .filter((i) => i.route !== root)
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
      pathname === root ||
      pathname === `${root}/`
    ) {
      return dash?.label ?? t('admin.shell.title')
    }
    return t('admin.shell.title')
  }, [items, pathname, t])
}
