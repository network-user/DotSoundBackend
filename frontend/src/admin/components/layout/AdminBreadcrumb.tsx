import { useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAdminMenu } from '@/components/Admin/AdminContext'
import { getAdminPanelRoute } from '@/lib/adminPath'
import { Icon } from '@/components/Icon/Icon'

interface Crumb {
  label: string
  to?: string
}

export function AdminBreadcrumb() {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const items = useAdminMenu()

  const crumbs: Crumb[] = useMemo(() => {
    const root = getAdminPanelRoute()
    const result: Crumb[] = [
      {
        label: t('admin.shell.title', 'Admin'),
        to: root,
      },
    ]
    if (!items.length || pathname === root || pathname === `${root}/`) {
      return result
    }
    const sorted = items
      .filter((i) => i.route !== root)
      .sort((a, b) => b.route.length - a.route.length)
    const match = sorted.find(
      (i) => pathname === i.route || pathname.startsWith(`${i.route}/`),
    )
    if (match) {
      result.push({
        label: match.label,
        to: pathname === match.route ? undefined : match.route,
      })
      if (pathname !== match.route) {
        const tail = pathname.slice(match.route.length + 1)
        const segs = tail.split('/').filter(Boolean)
        for (let i = 0; i < segs.length; i++) {
          result.push({ label: decodeURIComponent(segs[i]) })
        }
      }
    } else {
      const profile = getAdminPanelRoute('/profile')
      if (pathname === profile || pathname.endsWith(profile)) {
        result.push({
          label: t('redesign.admin.profileTitle', 'Profile'),
        })
      }
    }
    return result
  }, [items, pathname, t])

  if (crumbs.length === 0) return null

  return (
    <nav className="admin-breadcrumb" aria-label="Breadcrumb">
      <ol>
        {crumbs.map((c, i) => {
          const isLast = i === crumbs.length - 1
          return (
            <li key={i} className="admin-breadcrumb__crumb">
              {!isLast && c.to ? (
                <button
                  type="button"
                  className="admin-breadcrumb__link"
                  onClick={() => navigate(c.to!)}
                >
                  {c.label}
                </button>
              ) : (
                <span
                  className={
                    isLast
                      ? 'admin-breadcrumb__current'
                      : 'admin-breadcrumb__link'
                  }
                  aria-current={isLast ? 'page' : undefined}
                >
                  {c.label}
                </span>
              )}
              {!isLast ? (
                <span className="admin-breadcrumb__sep" aria-hidden>
                  <Icon name="chevron-right" size={12} />
                </span>
              ) : null}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
