import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { hapticSelection } from '@/lib/telegram'

interface NavItem {
  path: string
  icon: string
  labelKey: string
}

const NAV_ITEMS: NavItem[] = [
  { path: '/', icon: 'home', labelKey: 'nav.home' },
  { path: '/search', icon: 'search', labelKey: 'nav.search' },
  { path: '/library', icon: 'layers', labelKey: 'nav.library' },
  { path: '/chats', icon: 'message-circle', labelKey: 'nav.chats' },
  { path: '/profile', icon: 'user', labelKey: 'nav.profile' },
]

export function BottomNav() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  const handleNavigate = (path: string) => {
    if (location.pathname !== path) hapticSelection()
    navigate(path)
  }

  return (
    <nav id="nav" aria-label="Основная навигация">
      {NAV_ITEMS.map(({ path, icon, labelKey }) => {
        const active = isActive(path)
        const label = t(labelKey)
        return (
          <button
            key={path}
            className={`nav-btn${active ? ' active' : ''}`}
            onClick={() => handleNavigate(path)}
            aria-label={label}
            aria-current={
              active ? 'page' : undefined
            }
          >
            {active && (
              <span className="nav-btn__indicator" aria-hidden />
            )}
            <span className="nav-icon">
              <Icon name={icon} size={20} />
            </span>
            <span className="nav-label">
              {label}
            </span>
          </button>
        )
      })}
    </nav>
  )
}
