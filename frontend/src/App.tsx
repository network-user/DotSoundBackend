import {
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  Component,
  type ReactNode,
  type ErrorInfo,
} from 'react'

class ErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false }
  static getDerivedStateFromError() { return { hasError: true } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('[ErrorBoundary]', error, info) }
  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="error-boundary-fallback">
          <p>Что-то пошло не так</p>
          <button onClick={() => this.setState({ hasError: false })}>Попробовать снова</button>
        </div>
      )
    }
    return this.props.children
  }
}

function RouteFallback({
  timeoutMs = 8000,
}: {
  timeoutMs?: number
}) {
  const [stuck, setStuck] = useState(false)
  useEffect(() => {
    const id = window.setTimeout(
      () => setStuck(true),
      timeoutMs,
    )
    return () => window.clearTimeout(id)
  }, [timeoutMs])
  if (stuck) {
    return (
      <div className="error-boundary-fallback">
        <p>Не удалось загрузить раздел</p>
        <button
          onClick={() => window.location.reload()}
        >
          Перезагрузить
        </button>
      </div>
    )
  }
  return <div className="loader" />
}
import {
  Routes,
  Route,
  useLocation,
  useNavigate,
} from 'react-router-dom'
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
import { OfflineBanner } from '@/components/ui/OfflineBanner'
import { InstallPrompt } from '@/components/PwaInstall/InstallPrompt'
import { QueueSheet } from '@/components/QueueSheet/QueueSheet'
import { BannedScreen } from '@/components/BannedScreen/BannedScreen'
import { SystemEventListener } from '@/components/Notifications/SystemEventListener'
import { TrackCardSheet } from '@/components/TrackCardSheet/TrackCardSheet'
import { useTrackDeepLink } from '@/hooks/useDeepLink'
import { HomeView } from '@/views/HomeView'
import {
  connectWS,
  disconnectWS,
  setWSTokenProvider,
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
const LegalDocView = lazy(() => import('@/views/LegalDocView').then(m => ({ default: m.LegalDocView })))
const DailyMixView = lazy(() => import('@/views/DailyMixView').then(m => ({ default: m.DailyMixView })))
const RadioView = lazy(() => import('@/views/RadioView').then(m => ({ default: m.RadioView })))
const AdminApp = lazy(() =>
  import('@/admin/AdminApp').then((m) => ({
    default: m.AdminApp,
  })),
)

function TrackDeepLinkRoute() {
  useTrackDeepLink()
  return null
}

function AnimatedRoutes({
  children,
}: {
  children: ReactNode
}) {
  const location = useLocation()
  const [displayed, setDisplayed] = useState(location)
  const lastKey = useRef(location.pathname)

  useEffect(() => {
    if (lastKey.current === location.pathname) return
    lastKey.current = location.pathname

    const doc = document as Document & {
      startViewTransition?: (
        cb: () => void,
      ) => unknown
    }
    if (typeof doc.startViewTransition === 'function') {
      doc.startViewTransition(() => {
        setDisplayed(location)
      })
    } else {
      setDisplayed(location)
    }
  }, [location])

  return (
    <Routes location={displayed}>{children}</Routes>
  )
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
  const [artistId, setArtistId] = useState<
    number | null
  >(null)
  const [authError, setAuthError] = useState<
    string | null
  >(null)
  const [authDebug, setAuthDebug] = useState<
    Record<string, string>
  >({})
  const [needsOnboarding, setNeedsOnboarding] =
    useState(false)
  const [bannedReason, setBannedReason] = useState<
    string | null
  >(null)
  const initCalled = useRef(false)

  useEffect(() => {
    if (initCalled.current) return
    initCalled.current = true
    setWSTokenProvider(() => api.getToken())

    const init = async () => {
      let authenticated = false
      const debug: Record<string, string> = {}

      let initData = getInitData()

      debug.sdkInitData = String(
        tg.initData ? tg.initData.length : 0,
      )
      debug.nativeInitData = String(
        window.Telegram?.WebApp?.initData
          ? window.Telegram.WebApp.initData
              .length
          : 0,
      )
      debug.platform =
        (tg as { platform?: string })
          .platform ?? 'unknown'

      if (!initData) {
        await new Promise((r) =>
          setTimeout(r, 300),
        )
        initData = getInitData()
        debug.sdkInitDataRetry = String(
          tg.initData ? tg.initData.length : 0,
        )
        debug.nativeInitDataRetry = String(
          window.Telegram?.WebApp?.initData
            ? window.Telegram.WebApp.initData
                .length
            : 0,
        )
      }

      const hasTelegramContext =
        Boolean(initData)
      debug.resolved = String(hasTelegramContext)

      console.info(
        '[App] init',
        'sdk.initData:',
        debug.sdkInitData,
        'native.initData:',
        debug.nativeInitData,
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

      if (hasTelegramContext) {
        try {
          const authRes =
            await api.authTelegram(initData)
          if (authRes?.access_token) {
            connectWS(authRes.access_token)
            authenticated = true
            debug.authResult = 'ok'
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
          debug.authError = msg

          try {
            await new Promise((r) =>
              setTimeout(r, 500),
            )
            const retryRes =
              await api.authTelegram(
                getInitData(),
              )
            if (retryRes?.access_token) {
              connectWS(retryRes.access_token)
              authenticated = true
              debug.authResult = 'ok (retry)'
            }
          } catch (retryErr) {
            const retryMsg =
              retryErr instanceof Error
                ? retryErr.message
                : String(retryErr)
            debug.authRetryError = retryMsg
            setAuthError(
              `Telegram auth: ${msg}`,
            )
          }
        }
      } else {
        debug.authResult = 'skipped (no initData)'
      }

      if (!authenticated) {
        const restored = api.restoreSession()
        if (restored?.token) {
          connectWS(restored.token)
          authenticated = true
          debug.storedToken = 'restored'
        } else {
          debug.storedToken = 'none/expired'
        }
      }

      if (!authenticated) {
        setNeedsAuth(true)
      } else {
        try {
          window.dispatchEvent(
            new Event('app-auth-ready'),
          )
        } catch {
          /* ignore */
        }
      }

      setAuthDebug(debug)
      api.setOnUnauthorized(() => {
        disconnectWS()
        setNeedsAuth(true)
      })
      api.setOnAccountBlocked((reason) => {
        setBannedReason(reason || 'не указана')
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

  if (bannedReason) {
    return (
      <BannedScreen
        reason={bannedReason}
        onContact={() => {
          window.open(
            'mailto:support@dotsound.app',
            '_blank',
          )
        }}
        onLogout={handleLogout}
      />
    )
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
        debugInfo={authDebug}
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
      <OfflineBanner />
      <main id="main">
        <ErrorBoundary>
        <Suspense fallback={<RouteFallback />}>
        <AnimatedRoutes>
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
          <Route path="/legal/:docId" element={<LegalDocView />} />
          <Route path="/daily-mix" element={<DailyMixView />} />
          <Route path="/radio" element={<RadioView />} />
          <Route path="/admin/*" element={<AdminApp />} />
        </AnimatedRoutes>
        </Suspense>
        </ErrorBoundary>
      </main>
      <PlayerBar />
      <FullscreenLyrics />
      <Equalizer />
      <QueueSheet />
      <InstallPrompt />
      <SystemEventListener />
      <SettingsSheet
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onLogout={handleLogout}
      />
      <ComplaintModal />
      <TrackCardSheet
        onOpenAuthor={handleOpenAuthor}
        onOpenArtist={async (name) => {
          const res =
            await api.resolveArtistByName(name)
          if (res) setArtistId(res.id)
        }}
      />
      {authorId !== null && (
        <AuthorView
          authorId={authorId}
          onClose={handleCloseAuthor}
        />
      )}
      {artistId !== null && (
        <ArtistView
          artistId={artistId}
          onClose={() => setArtistId(null)}
        />
      )}
      <BottomNav />
    </div>
  )
}
