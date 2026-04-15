import { lazy, Suspense, useEffect, useState } from 'react'
import { Routes, Route, useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { tg, getInitData } from '@/lib/telegram'
import { AuthScreen } from '@/components/Auth/AuthScreen'
import { Onboarding } from '@/components/Onboarding/Onboarding'
import { ArtistView } from '@/components/ArtistView/ArtistView'
import { AuthorView } from '@/components/AuthorView/AuthorView'
import { BottomNav } from '@/components/BottomNav/BottomNav'
import { ComplaintModal } from '@/components/ComplaintModal/ComplaintModal'
import { SettingsSheet } from '@/components/Settings/SettingsSheet'
import { Equalizer } from '@/components/Equalizer/Equalizer'
import { FullscreenLyrics } from '@/components/FullscreenLyrics/FullscreenLyrics'
import { PlayerBar } from '@/components/PlayerBar/PlayerBar'
import { TrackCardSheet } from '@/components/TrackCardSheet/TrackCardSheet'
import { useTrackDeepLink } from '@/hooks/useDeepLink'
import { HomeView } from '@/views/HomeView'
import {
  connectWS,
  disconnectWS,
} from '@/lib/ws'
import { useLikes } from '@/store/LikesContext'

const SearchView = lazy(() => import('@/views/SearchView').then(m => ({ default: m.SearchView })))
const UploadView = lazy(() => import('@/views/UploadView').then(m => ({ default: m.UploadView })))
const LikedView = lazy(() => import('@/views/LikedView').then(m => ({ default: m.LikedView })))
const PlaylistsView = lazy(() => import('@/views/PlaylistsView').then(m => ({ default: m.PlaylistsView })))
const ChatsView = lazy(() => import('@/views/ChatsView').then(m => ({ default: m.ChatsView })))
const ChatView = lazy(() => import('@/views/ChatView').then(m => ({ default: m.ChatView })))
const ProfileView = lazy(() => import('@/views/ProfileView').then(m => ({ default: m.ProfileView })))
const LegalView = lazy(() => import('@/views/LegalView').then(m => ({ default: m.LegalView })))
const DailyMixView = lazy(() => import('@/views/DailyMixView').then(m => ({ default: m.DailyMixView })))
const RadioView = lazy(() => import('@/views/RadioView').then(m => ({ default: m.RadioView })))

function TrackDeepLinkRoute() {
  useTrackDeepLink()
  return null
}

export function App() {
  const { reloadLikes } = useLikes()
  const navigate = useNavigate()
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
  const [authError, setAuthError] = useState<
    string | null
  >(null)
  const [needsOnboarding, setNeedsOnboarding] =
    useState(false)

  useEffect(() => {
    const init = async () => {
      let authenticated = false
      const initData = getInitData()
      const hasTelegramContext =
        Boolean(initData)

      console.info(
        '[App] init',
        'sdk.initData:',
        tg.initData ? tg.initData.length : 0,
        'native.initData:',
        window.Telegram?.WebApp?.initData
          ? window.Telegram.WebApp.initData
              .length
          : 0,
        'resolved:',
        hasTelegramContext,
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
          // fall through
        }
      }

      try {
        if (
          !authenticated &&
          hasTelegramContext
        ) {
          const authRes =
            await api.authTelegram(initData)
          if (authRes?.access_token) {
            connectWS(authRes.access_token)
            authenticated = true
          }
        }
      } catch (err) {
        const msg =
          err instanceof Error
            ? err.message
            : String(err)
        console.error(
          '[App] Telegram auth failed:',
          msg,
        )
        setAuthError(
          `Telegram auth: ${msg}`,
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
      api.getOnboardingStatus()
        .then(s => {
          if (!s.onboarding_completed) {
            setNeedsOnboarding(true)
          }
        })
        .catch(() => {})
    }
  }, [needsAuth])

  const handleOpenAuthor = (id: number) =>
    setAuthorId(id)
  const handleCloseAuthor = () =>
    setAuthorId(null)
  const handleLogout = () => {
    disconnectWS()
    api.logout()
    setSettingsOpen(false)
    setNeedsAuth(true)
    navigate('/')
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
          setAuthError(null)
          setNeedsAuth(false)
          reloadLikes()
        }}
        error={authError}
      />
    )
  }

  if (needsOnboarding) {
    return (
      <Onboarding
        onComplete={() => {
          setNeedsOnboarding(false)
          reloadLikes()
        }}
      />
    )
  }

  return (
    <div id="app">
      <main id="main">
        <Suspense fallback={<div className="loader" />}>
        <Routes>
          <Route path="/" element={<HomeView />} />
          <Route path="/search" element={<SearchView />} />
          <Route path="/upload" element={<UploadView />} />
          <Route path="/liked" element={<LikedView />} />
          <Route path="/playlists" element={<PlaylistsView />} />
          <Route
            path="/chats"
            element={
              <ChatsView
                onOpenAuthor={handleOpenAuthor}
              />
            }
          />
          <Route path="/chats/:id" element={<ChatView />} />
          <Route
            path="/profile"
            element={
              <ProfileView
                onOpenSettings={() =>
                  setSettingsOpen(true)
                }
              />
            }
          />
          <Route path="/track/:trackId" element={<TrackDeepLinkRoute />} />
          <Route path="/legal" element={<LegalView />} />
          <Route path="/daily-mix" element={<DailyMixView />} />
          <Route path="/radio" element={<RadioView />} />
        </Routes>
        </Suspense>
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
      <BottomNav />
    </div>
  )
}
