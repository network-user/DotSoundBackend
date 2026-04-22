import { useEffect, useState } from 'react'
import { LikedView } from '@/views/LikedView'
import { PlaylistsView } from '@/views/PlaylistsView'
import { OfflineList } from '@/components/Profile/OfflineList'
import { HistoryList } from '@/components/Profile/HistoryList'
import { hapticSelection } from '@/lib/telegram'

type Tab = 'liked' | 'playlists' | 'offline' | 'history'

const STORAGE_KEY = 'library-tab'

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'liked', label: 'Любимое' },
  { id: 'playlists', label: 'Плейлисты' },
  { id: 'offline', label: 'Скачанные' },
  { id: 'history', label: 'История' },
]

export function LibraryView() {
  const [tab, setTab] = useState<Tab>(() => {
    try {
      const v = localStorage.getItem(
        STORAGE_KEY,
      ) as Tab | null
      return v || 'liked'
    } catch {
      return 'liked'
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, tab)
    } catch {
      /* ignore */
    }
  }, [tab])

  const handleTab = (next: Tab) => {
    if (next !== tab) hapticSelection()
    setTab(next)
  }

  return (
    <section
      id="view-library"
      className="view active"
    >
      <div className="library-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`library-tab${tab === t.id ? ' active' : ''}`}
            onClick={() => handleTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="library-content">
        {tab === 'liked' && <LikedView />}
        {tab === 'playlists' && <PlaylistsView />}
        {tab === 'offline' && <OfflineList />}
        {tab === 'history' && <HistoryList />}
      </div>
    </section>
  )
}
