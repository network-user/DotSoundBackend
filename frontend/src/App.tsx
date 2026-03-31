import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { tg } from '@/lib/telegram'
import { AuthorView } from '@/components/AuthorView/AuthorView'
import { BottomNav, type ViewName } from '@/components/BottomNav/BottomNav'
import { ComplaintModal } from '@/components/ComplaintModal/ComplaintModal'
import { PlayerBar } from '@/components/PlayerBar/PlayerBar'
import { TrackCardSheet } from '@/components/TrackCardSheet/TrackCardSheet'
import { useDeepLink } from '@/hooks/useDeepLink'
import { HomeView } from '@/views/HomeView'
import { LikedView } from '@/views/LikedView'
import { PlaylistsView } from '@/views/PlaylistsView'
import { ProfileView } from '@/views/ProfileView'
import { SearchView } from '@/views/SearchView'
import { UploadView } from '@/views/UploadView'

export function App() {
  const [activeView, setActiveView] = useState<ViewName>('home')
  const [authorId, setAuthorId] = useState<number | null>(null)
  const [isInitialized, setIsInitialized] = useState(false)

  useEffect(() => {
    const init = async () => {
      try {
        await api.authTelegram(tg.initData)
      } catch (err) {
        console.error('[App] Auth failed:', err)
      } finally {
        // Even if auth fails, we initialize so the user can see public content if needed, 
        // though most endpoints will 401 until they fix their Telegram session.
        setIsInitialized(true)
      }
    }
    init()
  }, [])

  useDeepLink()

  if (!isInitialized) {
    return (
      <div className="splash-screen">
        <div className="dot-loader">
          <div className="dot" />
          <div className="dot" />
          <div className="dot" />
        </div>
        <p>Loading session...</p>
      </div>
    )
  }

  const handleOpenAuthor = (id: number) => setAuthorId(id)
  const handleCloseAuthor = () => setAuthorId(null)

  return (
    <div id="app">
      <main id="main">
        <HomeView active={activeView === 'home'} />
        <SearchView active={activeView === 'search'} />
        <UploadView active={activeView === 'upload'} onNavigate={setActiveView} />
        <LikedView active={activeView === 'liked'} />
        <PlaylistsView active={activeView === 'playlists'} />
        <ProfileView
          active={activeView === 'profile'}
          onNavigate={setActiveView}
        />
      </main>
      <PlayerBar />
      <ComplaintModal />
      <TrackCardSheet onOpenAuthor={handleOpenAuthor} />
      {authorId !== null && (
        <AuthorView authorId={authorId} onClose={handleCloseAuthor} />
      )}
      <BottomNav activeView={activeView} onSwitch={setActiveView} />
    </div>
  )
}
