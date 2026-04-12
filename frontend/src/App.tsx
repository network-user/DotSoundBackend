import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import {
  tg,
} from '@/lib/telegram'
import { TelegramAuth } from '@/components/Auth/TelegramAuth'
import { ArtistView } from '@/components/ArtistView/ArtistView'
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
import { ChatView } from '@/views/ChatView'
import { ChatsView } from '@/views/ChatsView'
import { PlaylistsView } from '@/views/PlaylistsView'
import { ProfileView } from '@/views/ProfileView'
import { SearchView } from '@/views/SearchView'
import { UploadView } from '@/views/UploadView'
import { connectWS } from '@/lib/ws'

export function App() {
  const [activeView, setActiveView] =
    useState<ViewName>('home')
  const [authorId, setAuthorId] = useState<
    number | null
  >(null)
  const [isInitialized, setIsInitialized] =
    useState(false)
  const [needsAuth, setNeedsAuth] =
    useState(false)
  const [settingsOpen, setSettingsOpen] =
    useState(false)
  const [artistName, setArtistName] = useState<
    string | null
  >(null)
  const [openChatId, setOpenChatId] = useState<
    number | null
  >(null)
  const [openChatTitle, setOpenChatTitle] =
    useState<string | null>(null)

  useEffect(() => {
    const init = async () => {
      let authenticated = false
      try {
        const authRes = await api.authTelegram(tg.initData)
        if (authRes?.access_token) {
          connectWS(authRes.access_token)
          authenticated = true
        }
      } catch (err) {
        console.error('[App] Auth failed:', err)
      }

      if (!authenticated) {
        setNeedsAuth(true)
      }

      setIsInitialized(true)
    }
    init()
  }, [])

  useEffect(() => {
    if (needsAuth) return
    const token = api.getToken()
    if (token) {
      connectWS(token)
    }
  }, [needsAuth])

  useDeepLink()

  const handleOpenAuthor = (id: number) =>
    setAuthorId(id)
  const handleCloseAuthor = () =>
    setAuthorId(null)
  const handleLogout = () => {
    api.logout()
    setSettingsOpen(false)
    setNeedsAuth(true)
  }

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
        <ChatsView
          active={activeView === 'chats'}
          onOpenChat={(id, title) => {
            setOpenChatId(id)
            setOpenChatTitle(title ?? null)
            setActiveView('chat')
          }}
        />
        <ProfileView
          active={activeView === 'profile'}
          onNavigate={setActiveView}
          onOpenSettings={() =>
            setSettingsOpen(true)
          }
        />
      </main>
      <ChatView
        active={activeView === 'chat'}
        conversationId={openChatId}
        title={openChatTitle}
        onBack={() => setActiveView('chats')}
      />
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
        onOpenArtist={(name) =>
          setArtistName(name)
        }
      />
      {authorId !== null && (
        <AuthorView
          authorId={authorId}
          onClose={handleCloseAuthor}
        />
      )}
      {artistName !== null && (
        <ArtistView
          artistName={artistName}
          onClose={() => setArtistName(null)}
        />
      )}
      <BottomNav
        activeView={activeView}
        onSwitch={setActiveView}
      />
    </div>
  )
}
