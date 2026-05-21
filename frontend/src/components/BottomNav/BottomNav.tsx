import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  m,
  SPRING_LAYOUT,
  SPRING_SNAPPY,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'

interface NavItem {
  path: string
  morphName: string
  labelKey: string
}

const NAV_ITEMS: NavItem[] = [
  { path: '/', morphName: 'nav-home', labelKey: 'nav.home' },
  {
    path: '/library',
    morphName: 'nav-library',
    labelKey: 'nav.library',
  },
  { path: '/search', morphName: 'nav-search', labelKey: 'nav.search' },
  // [REGULATORY-DISABLED v1] чаты отключены, см. docs/REGULATORY_DISABLED.md
  // { path: '/chats', morphName: 'chats', labelKey: 'nav.chats' },
  {
    path: '/profile',
    morphName: 'nav-profile',
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
      <div className="rb-nav__dock">
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
              <m.span
                className="rb-nav__content"
                animate={
                  reduce
                    ? undefined
                    : {
                        y: active ? -1 : 0,
                      }
                }
                transition={SPRING_SNAPPY}
              >
                <m.span
                  className="rb-nav__icon-wrap"
                  animate={
                    reduce
                      ? undefined
                      : {
                          scale: active ? 1.08 : 1,
                          y: active ? -1 : 0,
                        }
                  }
                  transition={SPRING_SNAPPY}
                >
                  <MorphIcon
                    name={morphName}
                    filled={active}
                    size={22}
                  />
                  {active && !reduce && (
                    <m.span
                      key={`ring-${path}`}
                      className="rb-nav__ring"
                      initial={{ opacity: 0.55, scale: 0.62 }}
                      animate={{ opacity: 0, scale: 1.34 }}
                      transition={TWEEN_FAST}
                      aria-hidden
                    />
                  )}
                </m.span>
                <m.span
                  className="rb-nav__label"
                  animate={
                    reduce
                      ? undefined
                      : {
                          opacity: active ? 1 : 0.68,
                          y: active ? 0 : 2,
                        }
                  }
                  transition={TWEEN_FAST}
                >
                  {label}
                </m.span>
              </m.span>
            </MotionPress>
          )
        })}
      </div>
    </nav>
  )
}
