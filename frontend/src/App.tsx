import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import {
  getInternalUserId,
  setInternalUserId,
  telegramId,
  tg,
} from '@/lib/telegram'
import { TelegramAuth } from '@/components/Auth/TelegramAuth'
import { AuthorView } from '@/components/AuthorView/AuthorView'
import {
  BottomNav,
  type ViewName,
} from '@/components/BottomNav/BottomNav'
import { ComplaintModal } from '@/components/ComplaintModal/ComplaintModal'
import { SettingsSheet } from '@/components/Settings/SettingsSheet'
import { Equalizer } from '@/components/Equalizer/Equalizer'
import { FullscreenLyrics } from '@/components/FullscreenLyrics/FullscreenLyrics'
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
  const [activeView, setActiveView] =
    useState<ViewName>('home')
  const [authorId, setAuthorId] = useState<
    number | null
  >(null)
  const [isInitialized, setIsInitialized] =
    useState(false)
  const [needsAuth, setNeedsAuth] = useState(false)

  useEffect(() => {
    const init = async () => {
      try {
        await api.authTelegram(tg.initData)
      } catch (err) {
        console.error('[App] Auth failed:', err)
      }

      if (!getInternalUserId() && telegramId) {
        try {
          const profile =
            await api.getUserProfile(telegramId)
          setInternalUserId(profile.id)
        } catch {}
      }

      if (!getInternalUserId()) {
        setNeedsAuth(true)
      }

      setIsInitialized(true)
    }
    init()
  }, [])

  useDeepLink()

  if (!isInitialized) {
    return (
      <div className="splash-screen">
        <div className="splash-logo">.sound</div>
        <div className="splash-dots">
          <span />
          <span />
          <span />
        </div>
      </div>
    )
  }

  if (needsAuth) {
    return (
      <TelegramAuth
        onAuth={() => setNeedsAuth(false)}
      />
    )
  }

  const [settingsOpen, setSettingsOpen] =
    useState(false)
  const handleOpenAuthor = (id: number) =>
    setAuthorId(id)
  const handleCloseAuthor = () => setAuthorId(null)
  const handleLogout = () => {
    api.logout()
    setSettingsOpen(false)
    setNeedsAuth(true)
  }

  return (
    <div id="app">
      <main id="main">
        <HomeView
          active={activeView === 'home'}
        />
        <SearchView
          active={activeView === 'search'}
        />
        <UploadView
          active={activeView === 'upload'}
          onNavigate={setActiveView}
        />
        <LikedView
          active={activeView === 'liked'}
        />
        <PlaylistsView
          active={activeView === 'playlists'}
        />
        <ProfileView
          active={activeView === 'profile'}
          onNavigate={setActiveView}
          onOpenSettings={() =>
            setSettingsOpen(true)
          }
        />
      </main>
      <PlayerBar />
      <FullscreenLyrics />
      <Equalizer />
      <SettingsSheet
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onLogout={handleLogout}
      />
      <ComplaintModal />
      <TrackCardSheet
        onOpenAuthor={handleOpenAuthor}
      />
      {authorId !== null && (
        <AuthorView
          authorId={authorId}
          onClose={handleCloseAuthor}
        />
      )}
      <BottomNav
        activeView={activeView}
        onSwitch={setActiveView}
      />
    </div>
  )
}
