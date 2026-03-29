export type ViewName = 'home' | 'search' | 'upload' | 'liked' | 'playlists' | 'profile'

interface NavItem {
  view: ViewName
  icon: string
  label: string
}

const NAV_ITEMS: NavItem[] = [
  { view: 'home',      icon: '◎', label: 'Главная' },
  { view: 'search',    icon: '⌕', label: 'Поиск' },
  { view: 'upload',    icon: '↑', label: 'Загрузить' },
  { view: 'playlists', icon: '▤', label: 'Плейлисты' },
  { view: 'profile',   icon: '◉', label: 'Профиль' },
]

interface Props {
  activeView: ViewName
  onSwitch: (view: ViewName) => void
}

export function BottomNav({ activeView, onSwitch }: Props) {
  return (
    <nav id="nav">
      {NAV_ITEMS.map(({ view, icon, label }) => (
        <button
          key={view}
          id={`nav-btn-${view}`}
          className={`nav-btn${activeView === view ? ' active' : ''}`}
          data-view={view}
          onClick={() => onSwitch(view)}
        >
          <span className="nav-icon">{icon}</span>
          <span className="nav-label">{label}</span>
        </button>
      ))}
    </nav>
  )
}
