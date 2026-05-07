import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  m,
  SPRING_LAYOUT,
  useReducedMotion,
} from '@/lib/motion'
import {
  hapticSelection,
} from '@/lib/telegram'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'

interface NavItem {
  path: string
  morphName: string
  labelKey: string
}

const NAV_ITEMS: NavItem[] = [
  { path: '/', morphName: 'home', labelKey: 'nav.home' },
  { path: '/search', morphName: 'search', labelKey: 'nav.search' },
  {
    path: '/library',
    morphName: 'library',
    labelKey: 'nav.library',
  },
  { path: '/chats', morphName: 'chats', labelKey: 'nav.chats' },
  {
    path: '/profile',
    morphName: 'profile',
    labelKey: 'nav.profile',
  },
]

export function BottomNav() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const reduce = useReducedMotion()

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  const handleNavigate = (path: string) => {
    if (location.pathname !== path) hapticSelection()
    navigate(path)
  }

  return (
    <nav
      id="nav"
      className="rb-nav glass--liquid"
      aria-label={t(
        'redesign.nav.mainAria',
        'Main navigation',
      )}
    >
      {NAV_ITEMS.map(({ path, morphName, labelKey }) => {
        const active = isActive(path)
        const label = t(labelKey)
        return (
          <MotionPress
            key={path}
            type="button"
            variant="ghost"
            haptic="selection"
            className={`rb-nav__btn${active ? ' is-active' : ''}`}
            ariaLabel={label}
            aria-current={active ? 'page' : undefined}
            onClick={() => handleNavigate(path)}
          >
            <span className="rb-nav__icon-wrap">
              {active && !reduce && (
                <m.span
                  layoutId="bn-indicator"
                  className="rb-nav__bubble"
                  transition={SPRING_LAYOUT}
                  aria-hidden
                />
              )}
              {active && reduce && (
                <span
                  className="rb-nav__bubble rb-nav__bubble--static"
                  aria-hidden
                />
              )}
              <MorphIcon
                name={morphName}
                filled={active}
                size={22}
              />
            </span>
            <span className="rb-nav__label">{label}</span>
          </MotionPress>
        )
      })}
    </nav>
  )
}
