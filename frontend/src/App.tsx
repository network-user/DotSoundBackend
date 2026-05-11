import {
  Fragment,
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  Component,
  type ReactNode,
  type ErrorInfo,
} from 'react'
import { flushSync } from 'react-dom'
import { useBrandLabel } from '@/lib/brand'
import { AppErrorFallback } from '@/components/AppErrorFallback'

class ErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode },
  { hasError: boolean; resetKey: number }
> {
  state = { hasError: false, resetKey: 0 }
  static getDerivedStateFromError() {
    return { hasError: true }
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info)
  }
  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <AppErrorFallback
            variant="crash"
            onPrimary={() =>
              this.setState((s) => ({
                hasError: false,
                resetKey: s.resetKey + 1,
              }))
            }
          />
        )
      )
    }
    return (
      <Fragment key={this.state.resetKey}>
        {this.props.children}
      </Fragment>
    )
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
      <AppErrorFallback
        variant="section"
        onPrimary={() => window.location.reload()}
      />
    )
  }
  return <div className="loader" />
}
import {
  Routes,
  Route,
  useLocation,
  useNavigate,
  Navigate,
} from 'react-router-dom'
import { api } from '@/lib/api'
import {
  markAuthSuccess,
  trackActivationEvent,
} from '@/lib/activation'
import { useOptionalPrefetch } from '@/store/PrefetchContext'
import { tg, getInitData } from '@/lib/telegram'
import { AuthScreen } from '@/components/Auth/AuthScreen'
import { OnboardingV2 } from '@/components/Onboarding/OnboardingV2'
import { WelcomeTutorial } from '@/components/Tutorial/WelcomeTutorial'
import { AuthorView } from '@/components/AuthorView/AuthorView'
import { BottomNav } from '@/components/BottomNav/BottomNav'
import { ComplaintModal } from '@/components/ComplaintModal/ComplaintModal'
import { SettingsSheet } from '@/components/Settings/SettingsSheet'
import { OauthConnectionsReturn } from '@/components/Settings/OauthConnectionsReturn'
import { Equalizer } from '@/components/Equalizer/Equalizer'
import { FullscreenLyrics } from '@/components/FullscreenLyrics/FullscreenLyrics'
import { PlayerBar } from '@/components/PlayerBar/PlayerBar'
import { OfflineBanner } from '@/components/ui/OfflineBanner'
import { ConsentBanner } from '@/components/Legal/ConsentBanner'
import { DynamicIslandHost } from '@/components/ui/DynamicIsland'
import { InstallPrompt } from '@/components/PwaInstall/InstallPrompt'
import {
  PwaOnboardingModal,
  shouldShowPwaOnboardingModal,
} from '@/components/PwaInstall/PwaOnboardingModal'
import { QueueSheet } from '@/components/QueueSheet/QueueSheet'
import { BannedScreen } from '@/components/BannedScreen/BannedScreen'
import { SystemEventListener } from '@/components/Notifications/SystemEventListener'
import { ImportActivityBanner } from '@/components/Import/ImportActivityBanner'
import { TrackCardSheet } from '@/components/TrackCardSheet/TrackCardSheet'
import { useTrackDeepLink } from '@/hooks/useDeepLink'
import { HomeView } from '@/views/HomeView'
import { NotFoundView } from '@/views/NotFoundView'
import {
  connectWS,
  disconnectWS,
  setWSTokenProvider,
} from '@/lib/ws'
import { stopAllLyricsTaskSubscriptions } from '@/store/lyricsTaskStore'
import {
  getConfiguredAdminPanelPath,
  normalizeAdminPathSegment,
  setAdminRuntimeConfig,
} from '@/lib/adminPath'
import { useLikes } from '@/store/LikesContext'
import { useUploadQueueAutoResume } from '@/lib/uploadQueueAutoResume'

const SearchView = lazy(() => import('@/views/SearchView').then(m => ({ default: m.SearchView })))
const UploadView = lazy(() => import('@/views/UploadView').then(m => ({ default: m.UploadView })))
const TrackEditView = lazy(() => import('@/views/TrackEditView').then(m => ({ default: m.TrackEditView })))
const TrashView = lazy(() => import('@/views/TrashView').then(m => ({ default: m.TrashView })))
const MyTopView = lazy(() => import('@/views/MyTopView').then(m => ({ default: m.MyTopView })))
const LibraryView = lazy(() => import('@/views/LibraryView').then(m => ({ default: m.LibraryView })))
// [REGULATORY-DISABLED v1] чаты отключены — см. docs/REGULATORY_DISABLED.md
// const ChatsView = lazy(() => import('@/views/ChatsView').then(m => ({ default: m.ChatsView })))
// const ChatView = lazy(() => import('@/views/ChatView').then(m => ({ default: m.ChatView })))
const ProfileView = lazy(() => import('@/views/ProfileView').then(m => ({ default: m.ProfileView })))
const LegalView = lazy(() => import('@/views/LegalView').then(m => ({ default: m.LegalView })))
const LegalDocView = lazy(() => import('@/views/LegalDocView').then(m => ({ default: m.LegalDocView })))
const DailyMixView = lazy(() => import('@/views/DailyMixView').then(m => ({ default: m.DailyMixView })))
const WeeklyMixView = lazy(() => import('@/views/WeeklyMixView').then(m => ({ default: m.WeeklyMixView })))
const UserChoiceView = lazy(() => import('@/views/UserChoiceView').then(m => ({ default: m.UserChoiceView })))
const WeeklyTopView = lazy(() => import('@/views/WeeklyTopView').then(m => ({ default: m.WeeklyTopView })))
const ForgottenTreasuresView = lazy(() =>
  import('@/views/ForgottenTreasuresView').then(m => ({
    default: m.ForgottenTreasuresView,
  })),
)
const RadioView = lazy(() => import('@/views/RadioView').then(m => ({ default: m.RadioView })))
const GenreMixView = lazy(() => import('@/views/GenreMixView').then(m => ({ default: m.GenreMixView })))
const ArtistStatsView = lazy(() => import('@/views/ArtistStatsView').then(m => ({ default: m.ArtistStatsView })))
const ArtistView = lazy(() => import('@/views/ArtistView').then(m => ({ default: m.ArtistView })))
const AlbumView = lazy(() => import('@/views/AlbumView').then(m => ({ default: m.AlbumView })))
const PlaylistView = lazy(() => import('@/views/PlaylistView').then(m => ({ default: m.PlaylistView })))
const GenreView = lazy(() => import('@/views/GenreView').then(m => ({ default: m.GenreView })))
const ExternalTrackView = lazy(() => import('@/views/ExternalTrackView').then(m => ({ default: m.ExternalTrackView })))
const ExternalAlbumView = lazy(() => import('@/views/ExternalAlbumView').then(m => ({ default: m.ExternalAlbumView })))
const NowPlayingView = lazy(() => import('@/views/NowPlayingView').then(m => ({ default: m.NowPlayingView })))
const RecapView = lazy(() => import('@/views/RecapView').then(m => ({ default: m.RecapView })))
const AdminApp = lazy(() =>
  import('@/admin/AdminApp').then((m) => ({
    default: m.AdminApp,
  })),
)

const WARM_BOOT_CACHE_KEY = 'ds:last-ready-at'
const WARM_BOOT_WINDOW_MS = 30 * 60 * 1000

function hasRecentWarmBoot(): boolean {
  try {
    const raw = sessionStorage.getItem(
      WARM_BOOT_CACHE_KEY,
    )
    if (!raw) {
      return false
    }
    const lastReadyAt = Number(raw)
    if (!Number.isFinite(lastReadyAt)) {
      return false
    }
    return Date.now() - lastReadyAt <= WARM_BOOT_WINDOW_MS
  } catch {
    return false
  }
}

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
        flushSync(() => {
          setDisplayed(location)
        })
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
  const brandLabel = useBrandLabel()
  const { reloadLikes } = useLikes()
  useUploadQueueAutoResume()
  const navigate = useNavigate()
  const location = useLocation()
  const prefetch = useOptionalPrefetch()
  const warmBoot = useRef(hasRecentWarmBoot())
  const [authorId, setAuthorId] = useState<
    number | null
  >(null)
  const [isInitialized, setIsInitialized] =
    useState(false)
  const [forceUnblockInit, setForceUnblockInit] =
    useState(false)
  const [needsAuth, setNeedsAuth] =
    useState(false)
  const [settingsOpen, setSettingsOpen] =
    useState(false)
  const [authError, setAuthError] = useState<
    string | null
  >(null)
  const [authDebug, setAuthDebug] = useState<
    Record<string, string>
  >({})
  const [needsOnboarding, setNeedsOnboarding] =
    useState(false)
  const [needsTutorial, setNeedsTutorial] = useState(false)
  const [showPwaModal, setShowPwaModal] = useState(false)
  const [bannedReason, setBannedReason] = useState<
    string | null
  >(null)
  const [adminPanelPath, setAdminPanelPath] = useState<
    string | null
  >(getConfiguredAdminPanelPath())
  const initCalled = useRef(false)
  const readyEventSent = useRef(false)

  const fetchAndApplyAdminPath = async () => {
    try {
      const authConfig = await api.getAuthConfig()
      const configuredPath = authConfig.admin_panel_path
      if (configuredPath) {
        const normalized =
          normalizeAdminPathSegment(configuredPath)
        setAdminRuntimeConfig({
          panelPath: normalized,
          apiPath: authConfig.admin_api_path ?? null,
        })
        setAdminPanelPath(normalized)
      } else {
        setAdminRuntimeConfig({
          panelPath: null,
          apiPath: null,
        })
        setAdminPanelPath(null)
      }
    } catch {
      setAdminRuntimeConfig({
        panelPath: null,
        apiPath: null,
      })
      setAdminPanelPath(null)
    }
  }

  useEffect(() => {
    if (initCalled.current) return
    initCalled.current = true
    setWSTokenProvider(() => api.getToken())
    let initSettled = false
    const initWatchdogId = window.setTimeout(() => {
      if (initSettled) return
      setNeedsAuth(true)
      setIsInitialized(true)
    }, 9000)

    const init = async () => {
      let authenticated = false
      const debug: Record<string, string> = {}

      let initData = getInitData()

      debug.sdkInitData = String(
        tg?.initData ? tg.initData.length : 0,
      )
      debug.nativeInitData = String(
        window.Telegram?.WebApp?.initData
          ? window.Telegram.WebApp.initData
              .length
          : 0,
      )
      debug.platform =
        (tg as { platform?: string })
          ?.platform ?? 'unknown'

      if (!initData) {
        await new Promise((r) =>
          setTimeout(r, 300),
        )
        initData = getInitData()
        debug.sdkInitDataRetry = String(
          tg?.initData ? tg.initData.length : 0,
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
      try {
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
              markAuthSuccess()
              trackActivationEvent('auth_success', {
                once: true,
                meta: { via: 'magic_link' },
              })
              api.setOnUnauthorized(() => {
                disconnectWS()
                setNeedsAuth(true)
              })
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
          await fetchAndApplyAdminPath()
          await api.syncSessionUserFlags()
          markAuthSuccess()
          trackActivationEvent('auth_success', {
            once: true,
            meta: {
              via: hasTelegramContext
                ? 'telegram_initdata'
                : 'restored_session',
            },
          })
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
      } finally {
        initSettled = true
        window.clearTimeout(initWatchdogId)
        setIsInitialized(true)
      }
    }
    init()
    return () => {
      initSettled = true
      window.clearTimeout(initWatchdogId)
    }
  }, [])

  useEffect(() => {
    if (isInitialized) return
    const id = window.setTimeout(() => {
      setForceUnblockInit(true)
      setNeedsAuth(true)
      setIsInitialized(true)
    }, 12000)
    return () => {
      window.clearTimeout(id)
    }
  }, [isInitialized])

  useEffect(() => {
    if (!isInitialized || needsAuth || !prefetch) return
    let cancelled = false
    api
      .getListenHistory(1)
      .then((data) => {
        if (cancelled) return
        const last = data?.items?.[0]
        if (!last) return
        void prefetch.prefetch([last], {
          context: 'continue_on_app_start',
          replaceContext: true,
        })
      })
      .catch(() => {
        /* ignore */
      })
    return () => {
      cancelled = true
    }
  }, [isInitialized, needsAuth, prefetch])

  useEffect(() => {
    if (!isInitialized || readyEventSent.current) {
      return
    }
    readyEventSent.current = true
    const id = window.setTimeout(() => {
      window.dispatchEvent(new Event('app-ready'))
    }, 120)
    return () => {
      window.clearTimeout(id)
    }
  }, [isInitialized])

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
    const nav = navigator as Navigator & {
      deviceMemory?: number
    }
    const cores = nav.hardwareConcurrency ?? 8
    const memoryGb = nav.deviceMemory ?? 8
    const isCoarsePointer =
      window.matchMedia?.('(pointer: coarse)')
        .matches ?? false
    const shouldUseLiteProfile =
      isCoarsePointer || cores <= 6 || memoryGb <= 4
    document.body.classList.toggle(
      'ds-perf-lite',
      shouldUseLiteProfile,
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
          } else if (!s.tutorial_seen) {
            setNeedsTutorial(true)
          }
        })
        .catch(() => {})
    }
  }, [needsAuth])

  useEffect(() => {
    setAuthorId(null)
  }, [location.pathname])

  // [REGULATORY-DISABLED v1] handler использовался только в
  // отключённом ChatsView. Восстановить вместе с чат-маршрутом.
  // const handleOpenAuthor = (id: number) =>
  //   setAuthorId(id)
  const handleCloseAuthor = () =>
    setAuthorId(null)
  const handleLogout = () => {
    disconnectWS()
    stopAllLyricsTaskSubscriptions()
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
    if (warmBoot.current) {
      return null
    }
    return (
      <div className="splash-screen">
        <div className="splash-logo">{brandLabel}</div>
        <div className="splash-dots">
          <span />
          <span />
          <span />
        </div>
        {forceUnblockInit && (
          <button
            type="button"
            className="splash-retry-btn"
            onClick={() => window.location.reload()}
          >
            Reload
          </button>
        )}
      </div>
    )
  }

  if (needsAuth) {
    return (
      <AuthScreen
        onAuth={() => {
          setAuthError(null)
          setNeedsAuth(false)
          markAuthSuccess()
          trackActivationEvent('auth_success', {
            once: true,
            meta: { via: 'auth_screen' },
          })
          reloadLikes()
          void fetchAndApplyAdminPath().finally(() => {
            try {
              window.dispatchEvent(
                new Event('app-auth-ready'),
              )
            } catch {
              /* ignore */
            }
          })
        }}
        error={authError}
        debugInfo={authDebug}
      />
    )
  }

  if (needsOnboarding) {
    return (
      <OnboardingV2
        onComplete={() => {
          setNeedsOnboarding(false)
          setNeedsTutorial(true)
          reloadLikes()
          if (shouldShowPwaOnboardingModal()) {
            setShowPwaModal(true)
          }
        }}
      />
    )
  }

  if (needsTutorial) {
    return (
      <WelcomeTutorial
        onComplete={() => {
          setNeedsTutorial(false)
          try {
            const pendingImport =
              window.localStorage.getItem(
                'ds_pending_import_open',
              ) === '1'
            if (pendingImport) {
              window.localStorage.removeItem(
                'ds_pending_import_open',
              )
              navigate('/profile?import=1')
            }
          } catch {
            /* ignore */
          }
        }}
      />
    )
  }

  return (
    <div id="app">
      <DynamicIslandHost />
      <OfflineBanner />
      <ConsentBanner />
      {!needsOnboarding && !needsAuth && <ImportActivityBanner />}
      <main id="main">
        <ErrorBoundary>
        <Suspense fallback={<RouteFallback />}>
        <AnimatedRoutes>
          <Route
            path="/"
            element={
              <HomeView
                onOpenArtist={(id) => navigate(`/artist/${id}`)}
              />
            }
          />
          <Route
            path="/search"
            element={
              <SearchView
                onOpenArtist={(id) => navigate(`/artist/${id}`)}
              />
            }
          />
          <Route path="/upload" element={<UploadView />} />
          <Route path="/track/:trackId/edit" element={<TrackEditView />} />
          <Route path="/trash" element={<TrashView />} />
          <Route path="/my-top" element={<MyTopView />} />
          <Route path="/library" element={<LibraryView />} />
          <Route
            path="/liked"
            element={
              <Navigate
                to="/library?tab=liked"
                replace
              />
            }
          />
          <Route
            path="/playlists"
            element={
              <Navigate
                to="/library?tab=playlists"
                replace
              />
            }
          />
          {/* [REGULATORY-DISABLED v1] чат-маршруты отключены.
          <Route
            path="/chats"
            element={
              <ChatsView
                onOpenAuthor={handleOpenAuthor}
              />
            }
          />
          <Route path="/chats/:id" element={<ChatView />} />
          */}
          <Route
            path="/chats"
            element={<Navigate to="/" replace />}
          />
          <Route
            path="/chats/:id"
            element={<Navigate to="/" replace />}
          />
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
          <Route
            path="/settings/connections"
            element={<OauthConnectionsReturn />}
          />
          <Route path="/legal" element={<LegalView />} />
          <Route path="/legal/:docId" element={<LegalDocView />} />
          <Route path="/daily-mix" element={<DailyMixView />} />
          <Route path="/weekly-mix" element={<WeeklyMixView />} />
          <Route
            path="/user-choice"
            element={<UserChoiceView />}
          />
          <Route
            path="/weekly-top"
            element={<WeeklyTopView />}
          />
          <Route
            path="/forgotten-treasures"
            element={<ForgottenTreasuresView />}
          />
          <Route path="/radio" element={<RadioView />} />
          <Route path="/genre-mix/:genre" element={<GenreMixView />} />
          <Route path="/artist/:id/stats" element={<ArtistStatsView />} />
          <Route path="/artist/:id" element={<ArtistView />} />
          <Route path="/album/:id" element={<AlbumView />} />
          <Route path="/playlist/:id" element={<PlaylistView />} />
          <Route path="/genre/:slug" element={<GenreView />} />
          <Route path="/external/track/:id" element={<ExternalTrackView />} />
          <Route path="/external/album/:id" element={<ExternalAlbumView />} />
          <Route path="/now-playing" element={<NowPlayingView />} />
          <Route path="/recap" element={<RecapView />} />
          {adminPanelPath === 'admin' && (
            <Route path="/admin/*" element={<AdminApp />} />
          )}
          {adminPanelPath &&
            adminPanelPath !== 'admin' && (
              <Route
                path={`/${adminPanelPath}/*`}
                element={<AdminApp />}
              />
            )}
          {adminPanelPath !== 'admin' && (
            <Route
              path="/admin/*"
              element={<Navigate to="/" replace />}
            />
          )}
          <Route path="*" element={<NotFoundView />} />
        </AnimatedRoutes>
        </Suspense>
        </ErrorBoundary>
      </main>
      <PlayerBar />
      <FullscreenLyrics />
      <Equalizer />
      <QueueSheet />
      <InstallPrompt />
      {showPwaModal && (
        <PwaOnboardingModal
          onDismiss={() => setShowPwaModal(false)}
        />
      )}
      <SystemEventListener />
      <SettingsSheet
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onLogout={handleLogout}
      />
      <ComplaintModal />
      <TrackCardSheet
        onOpenArtist={async (name) => {
          const res =
            await api.resolveArtistByName(name)
          if (res) navigate(`/artist/${res.id}`)
        }}
      />
      {authorId !== null && (
        <AuthorView
          authorId={authorId}
          onClose={handleCloseAuthor}
        />
      )}
      <BottomNav />
    </div>
  )
}
