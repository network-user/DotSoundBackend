import { NavLink } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
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
    <nav
      className="admin-menu"
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
              ? 'admin-menu__item is-active'
              : 'admin-menu__item'
          }
        >
          {item.icon && (
            <Icon
              name={item.icon}
              size={18}
              className="admin-menu__icon"
            />
          )}
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
