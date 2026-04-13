import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import {
  getInternalUserId,
  tg,
} from '@/lib/telegram'
import { AuthScreen } from '@/components/Auth/AuthScreen'
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
import {
  connectWS,
  disconnectWS,
} from '@/lib/ws'
import { useLikes } from '@/store/LikesContext'

const CHAT_STATE_KEY_PREFIX = 'chat-state:'
const RESTORABLE_VIEWS: ViewName[] = [
  'home',
  'search',
  'upload',
  'liked',
  'playlists',
  'profile',
  'chats',
  'chat',
]

function getChatStateKey(userId: number) {
  return `${CHAT_STATE_KEY_PREFIX}${userId}`
}

function loadChatState(userId: number): {
  activeView: ViewName
  openChatId: number | null
  openChatTitle: string | null
} | null {
  try {
    const raw = localStorage.getItem(
      getChatStateKey(userId),
    )
    if (!raw) return null
    const parsed = JSON.parse(raw) as {
      activeView?: ViewName
      openChatId?: number | null
      openChatTitle?: string | null
    }
    if (
      !parsed.activeView ||
      !RESTORABLE_VIEWS.includes(
        parsed.activeView,
      )
    ) {
      return null
    }
    return {
      activeView: parsed.activeView,
      openChatId:
        typeof parsed.openChatId === 'number'
          ? parsed.openChatId
          : null,
      openChatTitle:
        typeof parsed.openChatTitle === 'string'
          ? parsed.openChatTitle
          : null,
    }
  } catch {
    return null
  }
}

function saveChatState(
  userId: number,
  state: {
    activeView: ViewName
    openChatId: number | null
    openChatTitle: string | null
  },
) {
  try {
    localStorage.setItem(
      getChatStateKey(userId),
      JSON.stringify(state),
    )
  } catch {}
}

export function App() {
  const { reloadLikes } = useLikes()
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
  const [navStateReady, setNavStateReady] =
    useState(false)

  useEffect(() => {
    const init = async () => {
      let authenticated = false
      const hasTelegramContext = Boolean(
        tg.initData,
      )

      const params = new URLSearchParams(
        window.location.search,
      )
      const magicToken = params.get('token')
      if (magicToken) {
        window.history.replaceState(
          {},
          '',
          window.location.pathname,
        )
        try {
          const res =
            await api.verifyMagicLink(
              magicToken,
            )
          if (
            res.access_token &&
            res.user_id &&
            !res.requires_2fa
          ) {
            connectWS(res.access_token)
            api.setOnUnauthorized(() => {
              disconnectWS()
              setNeedsAuth(true)
            })
            setIsInitialized(true)
            return
          }
        } catch {
          // fall through to other auth methods
        }
      }

      try {
        if (
          !authenticated &&
          hasTelegramContext
        ) {
          const authRes =
            await api.authTelegram(
              tg.initData,
            )
          if (authRes?.access_token) {
            connectWS(authRes.access_token)
            authenticated = true
          }
        }
      } catch (err) {
        console.error(
          '[App] Auth failed:',
          err,
        )
      }

      if (!authenticated) {
        const restored = api.restoreSession()
        if (restored?.token) {
          connectWS(restored.token)
          authenticated = true
        }
      }

      if (!authenticated) {
        setNeedsAuth(true)
      }

      api.setOnUnauthorized(() => {
        disconnectWS()
        setNeedsAuth(true)
      })
      setIsInitialized(true)
    }
    init()
  }, [])

  useEffect(() => {
    const mono =
      localStorage.getItem(
        'setting-monochrome',
      ) === 'true'
    document.body.classList.toggle(
      'monochrome',
      mono,
    )
  }, [])

  useEffect(() => {
    if (needsAuth) return
    const token = api.getToken()
    if (token) {
      connectWS(token)
    }
  }, [needsAuth])

  useEffect(() => {
    if (!isInitialized || needsAuth) {
      setNavStateReady(false)
      return
    }
    const userId = getInternalUserId()
    if (!userId) {
      setNavStateReady(true)
      return
    }

    let cancelled = false

    const restoreChatState = async () => {
      setNavStateReady(false)
      const saved = loadChatState(userId)
      if (!saved) {
        if (!cancelled) setNavStateReady(true)
        return
      }

      if (
        saved.activeView === 'chat' &&
        saved.openChatId !== null
      ) {
        try {
          const chats = await api.listChats()
          if (cancelled) return
          const exists = chats.some(
            (item) =>
              item.conversation.id ===
              saved.openChatId,
          )
          if (exists) {
            setOpenChatId(saved.openChatId)
            setOpenChatTitle(
              saved.openChatTitle,
            )
            setActiveView('chat')
          } else {
            setOpenChatId(null)
            setOpenChatTitle(null)
            setActiveView('chats')
          }
        } catch {
          if (cancelled) return
          setOpenChatId(null)
          setOpenChatTitle(null)
          setActiveView('chats')
        } finally {
          if (!cancelled) {
            setNavStateReady(true)
          }
        }
        return
      }

      setOpenChatId(null)
      setOpenChatTitle(null)
      setActiveView(saved.activeView)
      setNavStateReady(true)
    }

    void restoreChatState()

    return () => {
      cancelled = true
    }
  }, [isInitialized, needsAuth])

  useEffect(() => {
    if (
      !isInitialized ||
      needsAuth ||
      !navStateReady
    ) {
      return
    }
    const userId = getInternalUserId()
    if (!userId) return
    saveChatState(userId, {
      activeView,
      openChatId,
      openChatTitle,
    })
  }, [
    activeView,
    isInitialized,
    navStateReady,
    needsAuth,
    openChatId,
    openChatTitle,
  ])

  useDeepLink()

  const handleOpenAuthor = (id: number) =>
    setAuthorId(id)
  const handleCloseAuthor = () =>
    setAuthorId(null)
  const handleLogout = () => {
    disconnectWS()
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
      <AuthScreen
        onAuth={() => {
          setNeedsAuth(false)
          reloadLikes()
        }}
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
          onOpenAuthor={handleOpenAuthor}
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
