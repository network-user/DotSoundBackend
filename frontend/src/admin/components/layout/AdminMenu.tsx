import { LayoutGroup } from 'framer-motion'
import { NavLink } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { m, SPRING_LAYOUT } from '@/lib/motion'
import { useAdminMenu } from '@/components/Admin/AdminContext'

export function AdminMenu({
  onNavigate,
}: {
  onNavigate?: () => void
} = {}) {
  const items = useAdminMenu()
  if (!items.length) {
    return null
  }
  return (
    <LayoutGroup id="admin-sidebar-tabs">
      <nav
        className="admin-menu adm-r-menu"
        aria-label="Admin sections"
      >
        {items.map((item) => (
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
      </nav>
    </LayoutGroup>
  )
}
