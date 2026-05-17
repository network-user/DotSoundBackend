import { useCallback, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { LikedView } from '@/views/LikedView'
import { PlaylistsView } from '@/views/PlaylistsView'
import { ImportedView } from '@/views/ImportedView'
import { HistoryList } from '@/components/Profile/HistoryList'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { hapticSelection } from '@/lib/telegram'

const SHORTCUTS = [
  {
    id: 'daily',
    icon: 'calendar',
    labelKey: 'home.dayPlaylistTitle',
    route: '/daily-mix',
  },
  {
    id: 'weekly-top',
    icon: 'sparkle',
    labelKey: 'redesign.library.shortcutWeeklyTop',
    route: '/weekly-top',
  },
  {
    id: 'radio',
    icon: 'radio',
    labelKey: 'redesign.library.shortcutRadio',
    route: '/radio',
  },
  {
    id: 'my-top',
    icon: 'chart-bar',
    labelKey: 'redesign.library.shortcutMyTop',
    route: '/my-top',
  },
] as const

type Tab = 'liked' | 'playlists' | 'imported' | 'history'

const STORAGE_KEY = 'library-tab'

const TABS: Array<{
  id: Tab
  labelKey: string
}> = [
  { id: 'liked', labelKey: 'library.tabLiked' },
  { id: 'playlists', labelKey: 'library.tabPlaylists' },
  { id: 'imported', labelKey: 'library.tabImported' },
  { id: 'history', labelKey: 'library.tabHistory' },
]

function isTab(s: string | null): s is Tab {
  return (
    s === 'liked' ||
    s === 'playlists' ||
    s === 'imported' ||
    s === 'history'
  )
}

function tabFromStorageDefault(): Tab {
  try {
    const v = localStorage.getItem(
      STORAGE_KEY,
    ) as string | null
    if (v && isTab(v)) return v
  } catch {
    /* ignore */
  }
  return 'liked'
}

export function LibraryView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] =
    useSearchParams()
  const didSync = useRef(false)
  const urlTab = searchParams.get('tab')

  useEffect(() => {
    if (didSync.current) return
    if (isTab(urlTab)) {
      didSync.current = true
      return
    }
    const t =
      urlTab === null
        ? tabFromStorageDefault()
        : 'liked'
    setSearchParams({ tab: t }, { replace: true })
    didSync.current = true
  }, [setSearchParams, urlTab])

  const tab: Tab = isTab(urlTab)
    ? urlTab
    : urlTab === null
      ? tabFromStorageDefault()
      : 'liked'

  const handleTab = useCallback(
    (next: Tab) => {
      if (next !== tab) hapticSelection()
      setSearchParams({ tab: next }, { replace: true })
      try {
        localStorage.setItem(STORAGE_KEY, next)
      } catch {
        /* ignore */
      }
    },
    [setSearchParams, tab],
  )

  return (
    <section
      id="view-library"
      className="view active"
    >
      <div className="rd-lib-header">
        <h1 className="rd-lib-header__title">
          {t('nav.library')}
        </h1>
      </div>

      <div className="rd-lib-shortcuts">
        {SHORTCUTS.map((s) => (
          <MotionPress
            key={s.id}
            variant="subtle"
            haptic="selection"
            className="rd-lib-shortcut"
            onClick={() => navigate(s.route)}
          >
            <div className="rd-lib-shortcut__icon" aria-hidden>
              <Icon name={s.icon} size={20} />
            </div>
            <span className="rd-lib-shortcut__label">
              {t(s.labelKey)}
            </span>
          </MotionPress>
        ))}
      </div>

      <div className="library-tabs rd-lib-tabs">
        {TABS.map((row) => {
          const active = tab === row.id
          return (
            <MotionPress
              key={row.id}
              type="button"
              variant="ghost"
              haptic="selection"
              data-active={active ? 'true' : 'false'}
              className="rd-lib-tab library-tab"
              onClick={() => handleTab(row.id)}
            >
              {t(row.labelKey)}
            </MotionPress>
          )
        })}
      </div>
      <div className="library-content">
        {tab === 'liked' && <LikedView embedded />}
        {tab === 'playlists' && (
          <PlaylistsView embedded />
        )}
        {tab === 'imported' && (
          <ImportedView embedded />
        )}
        {tab === 'history' && <HistoryList />}
      </div>
    </section>
  )
}
