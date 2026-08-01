import {
  Fragment,
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  Component,
  type ComponentType,
  type ReactNode,
  type ErrorInfo,
} from 'react'
import { flushSync } from 'react-dom'
import { useBrandLabel } from '@/lib/brand'
import {
  isLegalPath,
  useRouteRobotsGuard,
} from '@/lib/pageSeo'
import { AppErrorFallback } from '@/components/AppErrorFallback'

class ErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false }
  static getDerivedStateFromError() {
    return { hasError: true }
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error)
    console.error('[ErrorBoundary] component stack:', info.componentStack)
  }
  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <AppErrorFallback
            variant="crash"
            onPrimary={() => {
              window.location.reload()
            }}
          />
        )
      )
    }
    return <Fragment>{this.props.children}</Fragment>
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
        onPrimary={() => {
          window.location.reload()
        }}
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
import { shouldUseLiteProfile } from '@/lib/glassPerformance'
import {
  markAuthSuccess,
  trackActivationEvent,
} from '@/lib/activation'
import { useOptionalPrefetch } from '@/store/PrefetchContext'
import { isTelegramMiniApp } from '@/lib/platform'
import { tg, getInitData } from '@/lib/telegram'
import { BottomNav } from '@/components/BottomNav/BottomNav'
import { PlayerBar } from '@/components/PlayerBar/PlayerBar'
import { OfflineBanner } from '@/components/ui/OfflineBanner'
import { DynamicIslandHost } from '@/components/ui/DynamicIsland'
import { shouldShowPwaOnboardingModal } from '@/components/PwaInstall/pwaOnboardingVisibility'
import { SystemEventListener } from '@/components/Notifications/SystemEventListener'
import { useTrackDeepLink } from '@/hooks/useDeepLink'
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
import { usePlayerMeta } from '@/store/PlayerContext'
import { useUploadQueueAutoResume } from '@/lib/uploadQueueAutoResume'
import { recoverFromStaleBuild } from '@/lib/staleBuildRecovery'

function lazyWithRetry<T extends ComponentType<any>>(
  fn: () => Promise<{ default: T }>,
) {
  return lazy(() =>
    fn().catch((firstError: unknown) =>
      new Promise<void>((r) => setTimeout(r, 1_000))
        .then(fn)
        .catch((secondError: unknown) => {
          recoverFromStaleBuild(secondError || firstError)
          throw secondError
        }),
    ),
  )
}

const AuthScreen = lazyWithRetry(() =>
  import('@/components/Auth/AuthScreen').then((m) => ({
    default: m.AuthScreen,
  })),
)
const OnboardingV2 = lazyWithRetry(() =>
  import('@/components/Onboarding/OnboardingV2').then((m) => ({
    default: m.OnboardingV2,
  })),
)
const WelcomeTutorial = lazyWithRetry(() =>
  import('@/components/Tutorial/WelcomeTutorial').then((m) => ({
    default: m.WelcomeTutorial,
  })),
)
const AuthorView = lazyWithRetry(() =>
  import('@/components/AuthorView/AuthorView').then((m) => ({
    default: m.AuthorView,
  })),
)
const ComplaintModal = lazyWithRetry(() =>
  import('@/components/ComplaintModal/ComplaintModal').then((m) => ({
    default: m.ComplaintModal,
  })),
)
const SettingsSheet = lazyWithRetry(() =>
  import('@/components/Settings/SettingsSheet').then((m) => ({
    default: m.SettingsSheet,
  })),
)
const OauthConnectionsReturn = lazyWithRetry(() =>
  import('@/components/Settings/OauthConnectionsReturn').then((m) => ({
    default: m.OauthConnectionsReturn,
  })),
)
const Equalizer = lazyWithRetry(() =>
  import('@/components/Equalizer/Equalizer').then((m) => ({
    default: m.Equalizer,
  })),
)
const FullscreenLyrics = lazyWithRetry(() =>
  import('@/components/FullscreenLyrics/FullscreenLyrics').then((m) => ({
    default: m.FullscreenLyrics,
  })),
)
const ConsentBanner = lazyWithRetry(() =>
  import('@/components/Legal/ConsentBanner').then((m) => ({
    default: m.ConsentBanner,
  })),
)
const TelegramBrowserHint = lazyWithRetry(() =>
  import('@/components/TelegramMiniApp/TelegramBrowserHint').then((m) => ({
    default: m.TelegramBrowserHint,
  })),
)
const InstallPrompt = lazyWithRetry(() =>
  import('@/components/PwaInstall/InstallPrompt').then((m) => ({
    default: m.InstallPrompt,
  })),
)
const PwaOnboardingModal = lazyWithRetry(() =>
  import('@/components/PwaInstall/PwaOnboardingModal').then((m) => ({
    default: m.PwaOnboardingModal,
  })),
)
const QueueSheet = lazyWithRetry(() =>
  import('@/components/QueueSheet/QueueSheet').then((m) => ({
    default: m.QueueSheet,
  })),
)
const BannedScreen = lazyWithRetry(() =>
  import('@/components/BannedScreen/BannedScreen').then((m) => ({
    default: m.BannedScreen,
  })),
)
const ImportActivityBanner = lazyWithRetry(() =>
  import('@/components/Import/ImportActivityBanner').then((m) => ({
    default: m.ImportActivityBanner,
  })),
)
const TrackCardSheet = lazyWithRetry(() =>
  import('@/components/TrackCardSheet/TrackCardSheet').then((m) => ({
    default: m.TrackCardSheet,
  })),
)
const HomeView = lazyWithRetry(() =>
  import('@/views/HomeView').then((m) => ({
    default: m.HomeView,
  })),
)
const NotFoundView = lazyWithRetry(() =>
  import('@/views/NotFoundView').then((m) => ({
    default: m.NotFoundView,
  })),
)
const SearchView = lazyWithRetry(() => import('@/views/SearchView').then(m => ({ default: m.SearchView })))
const UploadView = lazyWithRetry(() => import('@/views/UploadView').then(m => ({ default: m.UploadView })))
const TrackEditView = lazyWithRetry(() => import('@/views/TrackEditView').then(m => ({ default: m.TrackEditView })))
const ArtistProfileEditView = lazyWithRetry(() => import('@/views/ArtistProfileEditView').then(m => ({ default: m.ArtistProfileEditView })))
const TrashView = lazyWithRetry(() => import('@/views/TrashView').then(m => ({ default: m.TrashView })))
const MyTopView = lazyWithRetry(() => import('@/views/MyTopView').then(m => ({ default: m.MyTopView })))
const LibraryView = lazyWithRetry(() => import('@/views/LibraryView').then(m => ({ default: m.LibraryView })))
// [REGULATORY-DISABLED v1] чаты отключены — см. docs/REGULATORY_DISABLED.md
// const ChatsView = lazyWithRetry(() => import('@/views/ChatsView').then(m => ({ default: m.ChatsView })))
// const ChatView = lazyWithRetry(() => import('@/views/ChatView').then(m => ({ default: m.ChatView })))
const ProfileView = lazyWithRetry(() => import('@/views/ProfileView').then(m => ({ default: m.ProfileView })))
const PublicProfileView = lazyWithRetry(() => import('@/views/PublicProfileView').then(m => ({ default: m.PublicProfileView })))
const LegalView = lazyWithRetry(() => import('@/views/LegalView').then(m => ({ default: m.LegalView })))
const LegalDocView = lazyWithRetry(() => import('@/views/LegalDocView').then(m => ({ default: m.LegalDocView })))
const DailyMixView = lazyWithRetry(() => import('@/views/DailyMixView').then(m => ({ default: m.DailyMixView })))
const WeeklyMixView = lazyWithRetry(() => import('@/views/WeeklyMixView').then(m => ({ default: m.WeeklyMixView })))
const UserChoiceView = lazyWithRetry(() => import('@/views/UserChoiceView').then(m => ({ default: m.UserChoiceView })))
const WeeklyTopView = lazyWithRetry(() => import('@/views/WeeklyTopView').then(m => ({ default: m.WeeklyTopView })))
const ForgottenTreasuresView = lazyWithRetry(() =>
  import('@/views/ForgottenTreasuresView').then(m => ({
    default: m.ForgottenTreasuresView,
  })),
)
const RadioView = lazyWithRetry(() => import('@/views/RadioView').then(m => ({ default: m.RadioView })))
const GenreMixView = lazyWithRetry(() => import('@/views/GenreMixView').then(m => ({ default: m.GenreMixView })))
const ArtistStatsView = lazyWithRetry(() => import('@/views/ArtistStatsView').then(m => ({ default: m.ArtistStatsView })))
const ArtistView = lazyWithRetry(() => import('@/views/ArtistView').then(m => ({ default: m.ArtistView })))
const AlbumView = lazyWithRetry(() => import('@/views/AlbumView').then(m => ({ default: m.AlbumView })))
const PlaylistView = lazyWithRetry(() => import('@/views/PlaylistView').then(m => ({ default: m.PlaylistView })))
const GenreView = lazyWithRetry(() => import('@/views/GenreView').then(m => ({ default: m.GenreView })))
const ExternalTrackView = lazyWithRetry(() => import('@/views/ExternalTrackView').then(m => ({ default: m.ExternalTrackView })))
const ExternalAlbumView = lazyWithRetry(() => import('@/views/ExternalAlbumView').then(m => ({ default: m.ExternalAlbumView })))
const NowPlayingView = lazyWithRetry(() => import('@/views/NowPlayingView').then(m => ({ default: m.NowPlayingView })))
const RecapView = lazyWithRetry(() => import('@/views/RecapView').then(m => ({ default: m.RecapView })))
const AdminApp = lazyWithRetry(() =>
  import('@/admin/AdminApp').then((m) => ({
    default: m.AdminApp,
  })),
)

function TrackDeepLinkRoute({
  onOpenArtist,
}: {
  onOpenArtist: (id: number) => void
}) {
  useTrackDeepLink()
  return <HomeView onOpenArtist={onOpenArtist} />
}

function AnimatedRoutes({
  children,
}: {
  children: ReactNode
}) {
  const location = useLocation()
  const [displayed, setDisplayed] = useState(location)
  const prevLocationRef = useRef(location)

  useEffect(() => {
    const from = prevLocationRef.current
    const fromKey = routeLocationKey(from)
    const toKey = routeLocationKey(location)

    if (fromKey === toKey) return

    prevLocationRef.current = location
    const skipViewTransition =
      from.pathname === '/radio' || location.pathname === '/radio'

    const doc = document as Document & {
      startViewTransition?: (
        cb: () => void,
      ) => { finished?: Promise<unknown> }
    }
    if (
      skipViewTransition ||
      shouldSkipRouteMotion() ||
      typeof doc.startViewTransition !== 'function'
    ) {
      setDisplayed(location)
      return
    }

    const direction = getRouteTransitionDirection(
      from.pathname,
      location.pathname,
    )
    const root = document.documentElement
    root.dataset.routeTransition = direction

    const transition = doc.startViewTransition(() => {
      flushSync(() => {
        setDisplayed(location)
      })
    })
    const cleanup = () => {
      if (root.dataset.routeTransition === direction) {
        delete root.dataset.routeTransition
      }
    }
    if (transition.finished) {
      void transition.finished.finally(cleanup)
    } else {
      window.setTimeout(cleanup, 360)
    }
  }, [location])

  return (
    <div className="rb-route-transition">
      <Routes location={displayed}>{children}</Routes>
    </div>
  )
}

function routeLocationKey(location: {
  pathname: string
  search: string
  hash: string
}) {
  return `${location.pathname}${location.search}${location.hash}`
}

const ROUTE_ORDER = ['/', '/library', '/search', '/profile']

function getRouteRank(pathname: string): number | null {
  const index = ROUTE_ORDER.findIndex((path) => {
    if (path === '/') return pathname === '/'
    return pathname === path || pathname.startsWith(`${path}/`)
  })
  return index >= 0 ? index : null
}

function getRouteTransitionDirection(
  fromPath: string,
  toPath: string,
): 'forward' | 'back' | 'neutral' {
  const fromRank = getRouteRank(fromPath)
  const toRank = getRouteRank(toPath)
  if (
    fromRank !== null &&
    toRank !== null &&
    fromRank !== toRank
  ) {
    return toRank > fromRank ? 'forward' : 'back'
  }

  const fromDepth = fromPath.split('/').filter(Boolean).length
  const toDepth = toPath.split('/').filter(Boolean).length
  if (toDepth > fromDepth) return 'forward'
  if (toDepth < fromDepth) return 'back'
  return 'neutral'
}

function shouldSkipRouteMotion() {
  if (
    typeof window === 'undefined' ||
    typeof window.matchMedia !== 'function'
  ) {
    return false
  }
  try {
    return window.matchMedia(
      '(prefers-reduced-motion: reduce)',
    ).matches
  } catch {
    return false
  }
}

function useDeferredRender(
  active: boolean,
  delayMs = 260,
) {
  const [render, setRender] = useState(active)

  useEffect(() => {
    if (active) {
      setRender(true)
      return
    }
    const timer = window.setTimeout(
      () => setRender(false),
      delayMs,
    )
    return () => window.clearTimeout(timer)
  }, [active, delayMs])

  return render
}

function getTelegramStartParam(): string | null {
  const sdkParam = (tg as unknown as {
    initDataUnsafe?: { start_param?: unknown }
  })?.initDataUnsafe?.start_param
  if (typeof sdkParam === 'string' && sdkParam.trim()) {
    return sdkParam.trim()
  }

  const nativeParam = (window.Telegram?.WebApp as unknown as {
    initDataUnsafe?: { start_param?: unknown }
  } | undefined)?.initDataUnsafe?.start_param
  if (typeof nativeParam === 'string' && nativeParam.trim()) {
    return nativeParam.trim()
  }

  const params = new URLSearchParams(window.location.search)
  return (
    params.get('tgWebAppStartParam') ||
    params.get('startapp') ||
    params.get('start_param')
  )
}

function routeFromTelegramStartParam(param: string): string | null {
  const match = /^(profile|track|artist)_(\d+)$/.exec(param)
  if (!match) return null
  const [, kind, rawId] = match
  const id = Number(rawId)
  if (!Number.isInteger(id) || id <= 0) return null
  if (kind === 'profile') return `/profile/${id}`
  if (kind === 'track') return `/track/${id}`
  if (kind === 'artist') return `/artist/${id}`
  return null
}

interface LazyOverlaysProps {
  settingsOpen: boolean
  onCloseSettings: () => void
  onLogout: () => void
  showPwaModal: boolean
  onDismissPwa: () => void
  authorId: number | null
  onCloseAuthor: () => void
  onOpenTrackArtist: (name: string) => Promise<void>
}

function LazyOverlays({
  settingsOpen,
  onCloseSettings,
  onLogout,
  showPwaModal,
  onDismissPwa,
  authorId,
  onCloseAuthor,
  onOpenTrackArtist,
}: LazyOverlaysProps) {
  const {
    track,
    isLyricsOpen,
    isEqOpen,
    isQueueOpen,
    isComplaintOpen,
    isCardOpen,
  } = usePlayerMeta()

  const renderLyrics = useDeferredRender(
    Boolean(track && isLyricsOpen),
  )
  const renderEq = useDeferredRender(isEqOpen)
  const renderQueue = useDeferredRender(isQueueOpen)
  const renderComplaint = useDeferredRender(
    Boolean(track && isComplaintOpen),
  )
  const renderTrackCard = useDeferredRender(
    Boolean(track && isCardOpen),
  )
  const renderSettings = useDeferredRender(settingsOpen)

  return (
    <Suspense fallback={null}>
      {renderLyrics && <FullscreenLyrics />}
      {renderEq && <Equalizer />}
      {renderQueue && <QueueSheet />}
      <InstallPrompt />
      <TelegramBrowserHint />
      {showPwaModal && (
        <PwaOnboardingModal onDismiss={onDismissPwa} />
      )}
      {renderSettings && (
        <ErrorBoundary fallback={null}>
          <SettingsSheet
            open={settingsOpen}
            onClose={onCloseSettings}
            onLogout={onLogout}
          />
        </ErrorBoundary>
      )}
      {renderComplaint && <ComplaintModal />}
      {renderTrackCard && (
        <TrackCardSheet onOpenArtist={onOpenTrackArtist} />
      )}
      {authorId !== null && (
        <AuthorView
          authorId={authorId}
          onClose={onCloseAuthor}
        />
      )}
    </Suspense>
  )
}

export function App() {
  const brandLabel = useBrandLabel()
  const { reloadLikes } = useLikes()
  useUploadQueueAutoResume()
  useRouteRobotsGuard()
  const navigate = useNavigate()
  const location = useLocation()
  const prefetch = useOptionalPrefetch()
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
  const startParamHandledRef = useRef<string | null>(null)

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
      if (!api.hasSession()) {
        setNeedsAuth(true)
      }
      setIsInitialized(true)
    }, 25000)

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
      if (!initData && isTelegramMiniApp()) {
        const pollStart = Date.now()
        const deadline = pollStart + 4000
        while (!initData && Date.now() < deadline) {
          await new Promise((r) =>
            setTimeout(r, 120),
          )
          initData = getInitData()
        }
        debug.initDataPollMs = String(
          Date.now() - pollStart,
        )
        debug.sdkInitDataPoll = String(
          tg?.initData ? tg.initData.length : 0,
        )
        debug.nativeInitDataPoll = String(
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
              authenticated = true
              markAuthSuccess()
              setNeedsAuth(false)
              trackActivationEvent('auth_success', {
                once: true,
                meta: { via: 'magic_link' },
              })
            }
          } catch {
            // fall through
          }
        }

        if (hasTelegramContext && !authenticated) {
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
          const restored = await api.restoreSession()
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
          setNeedsAuth(false)
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
        if (api.hasSession()) {
          setNeedsAuth(false)
        }
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
      if (!api.hasSession()) {
        setNeedsAuth(true)
      }
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
    if (
      !isInitialized ||
      needsAuth ||
      needsOnboarding ||
      needsTutorial
    ) {
      return
    }
    const param = getTelegramStartParam()
    if (!param || startParamHandledRef.current === param) {
      return
    }
    const route = routeFromTelegramStartParam(param)
    if (!route) return
    startParamHandledRef.current = param
    if (location.pathname === route) return
    navigate(route, { replace: location.pathname === '/' })
  }, [
    isInitialized,
    location.pathname,
    navigate,
    needsAuth,
    needsOnboarding,
    needsTutorial,
  ])

  useEffect(() => {
    let mono = false
    try {
      mono =
        localStorage.getItem(
          'setting-monochrome',
        ) === 'true'
    } catch {
      mono = false
    }
    document.body.classList.toggle(
      'monochrome',
      mono,
    )
  }, [])

  useEffect(() => {
    document.body.classList.toggle(
      'ds-perf-lite',
      shouldUseLiteProfile(),
    )
  }, [])

  useEffect(() => {
    if (!isInitialized || needsAuth) return
    let cancelled = false
    const applyOnboardingStatus = async () => {
      let token = api.getToken()
      if (!token) {
        const restored = await api.restoreSession()
        token = restored?.token ?? api.getToken()
      }
      if (!token || cancelled) return
      connectWS(token)
      try {
        const status = await api.getOnboardingStatus()
        if (cancelled) return
        if (!status.onboarding_completed) {
          setNeedsTutorial(false)
          setNeedsOnboarding(true)
        } else if (!status.tutorial_seen) {
          setNeedsOnboarding(false)
          setNeedsTutorial(true)
        } else {
          setNeedsOnboarding(false)
          setNeedsTutorial(false)
        }
      } catch {
        /* ignore */
      }
    }
    void applyOnboardingStatus()
    return () => {
      cancelled = true
    }
  }, [isInitialized, needsAuth])

  useEffect(() => {
    const handleRecommendationsReset = () => {
      try {
        window.localStorage.removeItem('ds_pending_import_open')
        window.localStorage.removeItem('ds_pending_tutorial')
      } catch {
        /* ignore */
      }
      setNeedsTutorial(false)
      setNeedsOnboarding(true)
      navigate('/', { replace: true })
    }
    window.addEventListener(
      'ds-recommendations-reset',
      handleRecommendationsReset,
    )
    return () => {
      window.removeEventListener(
        'ds-recommendations-reset',
        handleRecommendationsReset,
      )
    }
  }, [navigate])

  useEffect(() => {
    setAuthorId(null)
  }, [location.pathname])

  // Deferred onboarding tutorial: when the user finishes onboarding
  // with "Import", we send them straight to /profile?import=1 and
  // store ds_pending_tutorial=1. As soon as they navigate away from
  // the import screen, surface the welcome tutorial once.
  useEffect(() => {
    if (needsOnboarding || needsAuth || needsTutorial) return
    try {
      const pending =
        window.localStorage.getItem('ds_pending_tutorial') === '1'
      if (!pending) return
      const onProfile = location.pathname.startsWith('/profile')
      if (!onProfile) {
        window.localStorage.removeItem('ds_pending_tutorial')
        setNeedsTutorial(true)
      }
    } catch {
      /* ignore */
    }
  }, [
    location.pathname,
    needsOnboarding,
    needsAuth,
    needsTutorial,
  ])

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
      <Suspense fallback={<div className="loader" />}>
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
      </Suspense>
    )
  }

  if (!isInitialized) {
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

  const onLegalRoute = isLegalPath(location.pathname)
  if (
    onLegalRoute &&
    (needsAuth || needsOnboarding || needsTutorial)
  ) {
    return (
      <div id="app">
        <main id="main">
          <ErrorBoundary>
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="/legal" element={<LegalView />} />
                <Route
                  path="/legal/:docId"
                  element={<LegalDocView />}
                />
                <Route
                  path="*"
                  element={<Navigate to="/legal" replace />}
                />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
    )
  }

  if (needsAuth) {
    return (
      <Suspense fallback={<div className="loader" />}>
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
      </Suspense>
    )
  }

  if (needsOnboarding) {
    return (
      <Suspense fallback={<div className="loader" />}>
        <OnboardingV2
          onComplete={() => {
            setNeedsOnboarding(false)
            reloadLikes()
            if (shouldShowPwaOnboardingModal()) {
              setShowPwaModal(true)
            }
            let pendingImport = false
            try {
              pendingImport =
                window.localStorage.getItem(
                  'ds_pending_import_open',
                ) === '1'
            } catch {
              /* ignore */
            }
            if (pendingImport) {
              // Open the import flow immediately. The welcome
              // tutorial is deferred until the user navigates
              // away from the import screen so the import flow
              // isn't blocked by an overlay.
              try {
                window.localStorage.removeItem(
                  'ds_pending_import_open',
                )
                window.localStorage.setItem(
                  'ds_pending_tutorial',
                  '1',
                )
              } catch {
                /* ignore */
              }
              navigate('/profile?import=1')
            } else {
              setNeedsTutorial(true)
            }
          }}
        />
      </Suspense>
    )
  }

  if (needsTutorial) {
    return (
      <Suspense fallback={<div className="loader" />}>
        <WelcomeTutorial
          onComplete={() => {
            setNeedsTutorial(false)
          }}
        />
      </Suspense>
    )
  }

  return (
    <div id="app">
      <DynamicIslandHost />
      <OfflineBanner />
      <Suspense fallback={null}>
        {!needsOnboarding && !needsAuth && !needsTutorial && (
          <ConsentBanner />
        )}
        {!needsOnboarding && !needsAuth && <ImportActivityBanner />}
      </Suspense>
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
          <Route path="/profile/artist" element={<ArtistProfileEditView />} />
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
            path="/profile/:userId"
            element={<PublicProfileView />}
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
          <Route
            path="/track/:trackId"
            element={
              <TrackDeepLinkRoute
                onOpenArtist={(id) => navigate(`/artist/${id}`)}
              />
            }
          />
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
      <SystemEventListener />
      <LazyOverlays
        settingsOpen={settingsOpen}
        onCloseSettings={() => setSettingsOpen(false)}
        onLogout={handleLogout}
        showPwaModal={showPwaModal}
        onDismissPwa={() => setShowPwaModal(false)}
        authorId={authorId}
        onCloseAuthor={handleCloseAuthor}
        onOpenTrackArtist={async (name) => {
          const res = await api.resolveArtistByName(name)
          if (res) navigate(`/artist/${res.id}`)
        }}
      />
      <BottomNav />
    </div>
  )
}
