import { useState } from 'react'
import { BottomNav, type ViewName } from '@/components/BottomNav/BottomNav'
import { ComplaintModal } from '@/components/ComplaintModal/ComplaintModal'
import { PlayerBar } from '@/components/PlayerBar/PlayerBar'
import { useDeepLink } from '@/hooks/useDeepLink'
import { HomeView } from '@/views/HomeView'
import { LikedView } from '@/views/LikedView'
import { SearchView } from '@/views/SearchView'
import { UploadView } from '@/views/UploadView'

export function App() {
  const [activeView, setActiveView] = useState<ViewName>('home')

  useDeepLink()

  return (
    <div id="app">
      <main id="main">
        <HomeView active={activeView === 'home'} />
        <SearchView active={activeView === 'search'} />
        <UploadView active={activeView === 'upload'} onNavigate={setActiveView} />
        <LikedView active={activeView === 'liked'} />
      </main>
      <PlayerBar />
      <ComplaintModal />
      <BottomNav activeView={activeView} onSwitch={setActiveView} />
    </div>
  )
}
