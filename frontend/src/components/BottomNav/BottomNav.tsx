import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'

interface NavItem {
  path: string
  icon: string
  labelKey: string
}

const NAV_ITEMS: NavItem[] = [
  { path: '/', icon: 'home', labelKey: 'nav.home' },
  { path: '/search', icon: 'search', labelKey: 'nav.search' },
  { path: '/chats', icon: 'message-circle', labelKey: 'nav.chats' },
  { path: '/upload', icon: 'upload', labelKey: 'nav.upload' },
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

  return (
    <nav id="nav">
      {NAV_ITEMS.map(({ path, icon, labelKey }) => (
        <button
          key={path}
          className={`nav-btn${isActive(path) ? ' active' : ''}`}
          onClick={() => navigate(path)}
        >
          <span className="nav-icon">
            <Icon name={icon} size={20} />
          </span>
          <span className="nav-label">
            {t(labelKey)}
          </span>
        </button>
      ))}
    </nav>
  )
}
