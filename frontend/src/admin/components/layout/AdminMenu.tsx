import { useMemo } from 'react'
import { LayoutGroup } from 'framer-motion'
import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { m, SPRING_LAYOUT } from '@/lib/motion'
import { useAdminMenu } from '@/components/Admin/AdminContext'

interface MenuItem {
  id: string
  label: string
  route: string
  icon?: string
  capability?: string | null
}

interface MenuGroup {
  id: string
  labelKey: string
  fallback: string
  match: (item: MenuItem) => boolean
}

const GROUPS: MenuGroup[] = [
  {
    id: 'overview',
    labelKey: 'admin.menu.groups.overview',
    fallback: 'Overview',
    match: (i) => /^(dashboard|home|overview)$/i.test(i.id),
  },
  {
    id: 'catalog',
    labelKey: 'admin.menu.groups.catalog',
    fallback: 'Catalog',
    match: (i) =>
      /^(tracks|albums|artists|playlists|lyrics)$/i.test(i.id),
  },
  {
    id: 'audience',
    labelKey: 'admin.menu.groups.audience',
    fallback: 'Audience',
    match: (i) =>
      /^(users|complaints|moderation)$/i.test(i.id),
  },
  {
    id: 'ops',
    labelKey: 'admin.menu.groups.ops',
    fallback: 'Operations',
    match: (i) =>
      /^(audio-compute|tasks|schedules|logs|metrics|containers|antivirus)$/i.test(
        i.id,
      ),
  },
  {
    id: 'trust',
    labelKey: 'admin.menu.groups.trust',
    fallback: 'Trust & config',
    match: (i) =>
      /^(audit|security|recsys|settings|profile)$/i.test(i.id),
  },
]

function groupItems(items: MenuItem[]) {
  const buckets = new Map<string, MenuItem[]>()
  const seen = new Set<string>()
  for (const g of GROUPS) buckets.set(g.id, [])
  buckets.set('other', [])
  for (const item of items) {
    let placed = false
    for (const g of GROUPS) {
      if (g.match(item)) {
        buckets.get(g.id)!.push(item)
        seen.add(item.id)
        placed = true
        break
      }
    }
    if (!placed) buckets.get('other')!.push(item)
  }
  return GROUPS.map((g) => ({
    id: g.id,
    labelKey: g.labelKey,
    fallback: g.fallback,
    items: buckets.get(g.id) ?? [],
  }))
    .concat({
      id: 'other',
      labelKey: 'admin.menu.groups.other',
      fallback: 'Other',
      items: buckets.get('other') ?? [],
    })
    .filter((g) => g.items.length > 0)
}

export function AdminMenu({
  onNavigate,
}: {
  onNavigate?: () => void
} = {}) {
  const { t } = useTranslation()
  const items = useAdminMenu()
  const groups = useMemo(() => groupItems(items), [items])
  if (!items.length) {
    return null
  }
  return (
    <LayoutGroup id="admin-sidebar-tabs">
      <nav
        className="admin-menu adm-r-menu"
        aria-label="Admin sections"
      >
        {groups.map((group, idx) => (
          <div
            key={group.id}
            className="admin-menu__group"
            role="group"
            aria-labelledby={`adm-menu-grp-${group.id}`}
          >
            <div
              id={`adm-menu-grp-${group.id}`}
              className="admin-menu__group-label"
            >
              {t(group.labelKey, group.fallback)}
            </div>
            {group.items.map((item) => (
              <NavLink
                key={item.id}
                to={item.route}
                end
                onClick={onNavigate}
                className={({ isActive }) =>
                  isActive
                    ? 'adm-r-menu__item admin-menu__item is-active'
                    : 'adm-r-menu__item admin-menu__item'
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <m.span
                        layoutId="admin-tab-indicator"
                        className="adm-r-menu__indicator"
                        transition={SPRING_LAYOUT}
                      />
                    )}
                    {item.icon && (
                      <Icon
                        name={item.icon}
                        size={18}
                        className="admin-menu__icon adm-r-menu__icon"
                      />
                    )}
                    <span className="adm-r-menu__label">
                      {item.label}
                    </span>
                  </>
                )}
              </NavLink>
            ))}
            {idx < groups.length - 1 ? (
              <div
                className="admin-menu__divider"
                role="separator"
                aria-hidden
              />
            ) : null}
          </div>
        ))}
      </nav>
    </LayoutGroup>
  )
}
