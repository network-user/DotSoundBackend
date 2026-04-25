import { useCallback, useEffect, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { LikedView } from '@/views/LikedView'
import { PlaylistsView } from '@/views/PlaylistsView'
import { OfflineList } from '@/components/Profile/OfflineList'
import { HistoryList } from '@/components/Profile/HistoryList'
import { Icon } from '@/components/Icon/Icon'
import { hapticSelection } from '@/lib/telegram'

type Tab = 'liked' | 'playlists' | 'offline' | 'history'

const STORAGE_KEY = 'library-tab'

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'liked', label: 'Любимое' },
  { id: 'playlists', label: 'Плейлисты' },
  { id: 'offline', label: 'Скачанные' },
  { id: 'history', label: 'История' },
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
        <button
          className="playlist-card"
          style={{ width: '100%' }}
          onClick={() => navigate('/daily-mix')}
        >
          <div style={{ fontSize: 32, lineHeight: 1 }}>📅</div>
          <div style={{ flex: 1, textAlign: 'left' }}>
            <div style={{ fontWeight: 600, fontSize: 15 }}>Плейлист дня</div>
            <div className="hint" style={{ fontSize: 12 }}>Персональная подборка + открытия</div>
          </div>
          <Icon name="chevron" size={18} />
        </button>
      </div>

      <div className="library-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`library-tab${tab === t.id ? ' active' : ''}`}
            onClick={() => handleTab(t.id)}
          >
            {t.label}
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
