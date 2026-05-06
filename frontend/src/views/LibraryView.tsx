import { useCallback, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { LikedView } from '@/views/LikedView'
import { PlaylistsView } from '@/views/PlaylistsView'
import { OfflineList } from '@/components/Profile/OfflineList'
import { HistoryList } from '@/components/Profile/HistoryList'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { SPRING_LAYOUT, m } from '@/lib/motion'
import { hapticSelection } from '@/lib/telegram'

type Tab = 'liked' | 'playlists' | 'offline' | 'history'

const STORAGE_KEY = 'library-tab'

const TABS: Array<{
  id: Tab
  labelKey: string
}> = [
  { id: 'liked', labelKey: 'library.tabLiked' },
  { id: 'playlists', labelKey: 'library.tabPlaylists' },
  { id: 'offline', labelKey: 'library.tabOffline' },
  { id: 'history', labelKey: 'library.tabHistory' },
]

function isTab(s: string | null): s is Tab {
  return (
    s === 'liked' ||
    s === 'playlists' ||
    s === 'offline' ||
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
      <div style={{ padding: '8px 16px 0' }}>
      <MotionPress
        variant="subtle"
        haptic="selection"
        className="rd-lib-daily playlist-card"
        onClick={() => navigate('/daily-mix')}
      >
        <div className="playlist-cover" aria-hidden>
          <Icon name="calendar" size={26} />
        </div>
        <div style={{ flex: 1, textAlign: 'left' }}>
          <div style={{ fontWeight: 600, fontSize: 15 }}>
            {t('home.dayPlaylistTitle')}
          </div>
          <div className="hint" style={{ fontSize: 12 }}>
            {t('home.dayPlaylistHint')}
          </div>
        </div>
        <Icon name="chevron" size={18} />
      </MotionPress>
      </div>

      <div className="library-tabs rd-lib-tabs">
        {TABS.map((row) => (
          <button
            key={row.id}
            type="button"
            data-active={tab === row.id ? 'true' : 'false'}
            className={`rd-lib-tab library-tab${tab === row.id ? ' active' : ''}`}
            onClick={() => handleTab(row.id)}
          >
            {tab === row.id && (
              <m.span
                className="rd-lib-tab-pill"
                layoutId="library-tab-pill"
                transition={SPRING_LAYOUT}
              />
            )}
            <span className="rd-lib-tab-label">
              {t(row.labelKey)}
            </span>
          </button>
        ))}
      </div>
      <div className="library-content">
        {tab === 'liked' && <LikedView embedded />}
        {tab === 'playlists' && (
          <PlaylistsView embedded />
        )}
        {tab === 'offline' && <OfflineList />}
        {tab === 'history' && <HistoryList />}
      </div>
    </section>
  )
}
