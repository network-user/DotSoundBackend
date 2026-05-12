import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAdminMenu } from '@/components/Admin/AdminContext'
import { getAdminPanelRoute } from '@/lib/adminPath'

export interface AdminCommand {
  id: string
  title: string
  subtitle?: string
  group?: string
  icon?: string
  keywords?: string[]
  run: () => void
}

export function useAdminCommands(onAfterRun?: () => void) {
  const navigate = useNavigate()
  const items = useAdminMenu()
  const { t } = useTranslation()

  return useMemo<AdminCommand[]>(() => {
    const commands: AdminCommand[] = items.map((item) => ({
      id: `nav-${item.id}`,
      title: item.label,
      subtitle: item.route,
      group: t('admin.cmdk.groups.nav', 'Navigate'),
      icon: item.icon,
      keywords: [item.id, item.label.toLowerCase()],
      run: () => {
        navigate(item.route)
        onAfterRun?.()
      },
    }))
    commands.push({
      id: 'nav-profile',
      title: t('redesign.admin.profileTitle', 'Profile'),
      subtitle: getAdminPanelRoute('/profile'),
      group: t('admin.cmdk.groups.nav', 'Navigate'),
      icon: 'user',
      keywords: ['profile', 'me', 'account'],
      run: () => {
        navigate(getAdminPanelRoute('/profile'))
        onAfterRun?.()
      },
    })
    return commands
  }, [items, navigate, onAfterRun, t])
}
