import { useState } from 'react'
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

  useDeepLink()

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
