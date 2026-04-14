import { useLocation, useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'

interface NavItem {
  path: string
  icon: string
  label: string
}

const NAV_ITEMS: NavItem[] = [
  { path: '/', icon: 'home', label: 'Главная' },
  {
    path: '/search',
    icon: 'search',
    label: 'Поиск',
  },
  {
    path: '/chats',
    icon: 'message-circle',
    label: 'Чаты',
  },
  {
    path: '/upload',
    icon: 'upload',
    label: 'Загрузить',
  },
  {
    path: '/profile',
    icon: 'user',
    label: 'Профиль',
  },
]

export function BottomNav() {
  const navigate = useNavigate()
  const location = useLocation()

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  return (
    <nav id="nav">
      {NAV_ITEMS.map(({ path, icon, label }) => (
        <button
          key={path}
          className={`nav-btn${isActive(path) ? ' active' : ''}`}
          onClick={() => navigate(path)}
        >
          <span className="nav-icon">
            <Icon name={icon} size={20} />
          </span>
          <span className="nav-label">
            {label}
          </span>
        </button>
      ))}
    </nav>
  )
}
