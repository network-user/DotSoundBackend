import {
  lazy,
  Suspense,
  useEffect,
  type ReactNode,
} from 'react'
import { useTranslation } from 'react-i18next'
import {
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'
import { Route, Routes } from 'react-router-dom'
import { api } from '@/lib/api'
import { StepUpProvider } from './components/auth/StepUpDialog'
import { AdminPromptProvider } from './components/layout/AdminPromptContext'
import { AdminShell } from './components/layout/AdminShell'
import {
  clearDeviceApprovalBrowserState,
  readPendingDeviceId,
} from './lib/adminDeviceApprovalSession'
import { adminApi } from './lib/adminApi'
import { setUserTokenProvider } from './lib/adminApi'
import { useAdminAuth } from './store/adminAuthStore'
import './styles/admin.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5_000,
    },
  },
})

const AdminInit = lazy(() =>
  import('./components/auth/AdminInit').then((m) => ({
    default: m.AdminInit,
  })),
)
const AdminLogin = lazy(() =>
  import('./components/auth/AdminLogin').then((m) => ({
    default: m.AdminLogin,
  })),
)
const DeviceApproval = lazy(() =>
  import('./components/auth/DeviceApproval').then((m) => ({
    default: m.DeviceApproval,
  })),
)

const AntivirusRoute = lazy(() =>
  import('./routes/AntivirusRoute').then((m) => ({
    default: m.AntivirusRoute,
  })),
)
const ArtistsRoute = lazy(() =>
  import('./routes/ArtistsRoute').then((m) => ({
    default: m.ArtistsRoute,
  })),
)
const StationGapRoute = lazy(() =>
  import('./routes/StationGapRoute').then((m) => ({
    default: m.StationGapRoute,
  })),
)
const AuditRoute = lazy(() =>
  import('./routes/AuditRoute').then((m) => ({
    default: m.AuditRoute,
  })),
)
const AudioComputeRoute = lazy(() =>
  import('./routes/AudioComputeRoute').then((m) => ({
    default: m.AudioComputeRoute,
  })),
)
const ComplaintsRoute = lazy(() =>
  import('./routes/ComplaintsRoute').then((m) => ({
    default: m.ComplaintsRoute,
  })),
)
const ContainersRoute = lazy(() =>
  import('./routes/ContainersRoute').then((m) => ({
    default: m.ContainersRoute,
  })),
)
const DashboardRoute = lazy(() =>
  import('./routes/DashboardRoute').then((m) => ({
    default: m.DashboardRoute,
  })),
)
const LogsRoute = lazy(() =>
  import('./routes/LogsRoute').then((m) => ({
    default: m.LogsRoute,
  })),
)
const MetricsRoute = lazy(() =>
  import('./routes/MetricsRoute').then((m) => ({
    default: m.MetricsRoute,
  })),
)
const NetworkRoute = lazy(() =>
  import('./routes/NetworkRoute').then((m) => ({
    default: m.NetworkRoute,
  })),
)
const SecurityRoute = lazy(() =>
  import('./routes/SecurityRoute').then((m) => ({
    default: m.SecurityRoute,
  })),
)
const SettingsRoute = lazy(() =>
  import('./routes/SettingsRoute').then((m) => ({
    default: m.SettingsRoute,
  })),
)
const SchedulesRoute = lazy(() =>
  import('./routes/SchedulesRoute').then((m) => ({
    default: m.SchedulesRoute,
  })),
)
const RecsysRoute = lazy(() =>
  import('./routes/RecsysRoute').then((m) => ({
    default: m.RecsysRoute,
  })),
)
const TasksRoute = lazy(() =>
  import('./routes/TasksRoute').then((m) => ({
    default: m.TasksRoute,
  })),
)
const AlbumDetailRoute = lazy(() =>
  import('./routes/AlbumDetailRoute').then((m) => ({
    default: m.AlbumDetailRoute,
  })),
)
const AlbumsListRoute = lazy(() =>
  import('./routes/AlbumsListRoute').then((m) => ({
    default: m.AlbumsListRoute,
  })),
)
const PlaylistDetailRoute = lazy(() =>
  import('./routes/PlaylistDetailRoute').then((m) => ({
    default: m.PlaylistDetailRoute,
  })),
)
const PlaylistsListRoute = lazy(() =>
  import('./routes/PlaylistsListRoute').then((m) => ({
    default: m.PlaylistsListRoute,
  })),
)
const AdminProfileRoute = lazy(() =>
  import('./routes/AdminProfileRoute').then((m) => ({
    default: m.AdminProfileRoute,
  })),
)
const TracksRoute = lazy(() =>
  import('./routes/TracksRoute').then((m) => ({
    default: m.TracksRoute,
  })),
)
const UsersRoute = lazy(() =>
  import('./routes/UsersRoute').then((m) => ({
    default: m.UsersRoute,
  })),
)

function AdminChunkFallback() {
  const { t } = useTranslation()
  return (
    <div className="admin-auth-screen adm-r-auth-stage">
      <div className="admin-auth-card">
        {t('admin.auth.checking')}
      </div>
    </div>
  )
}

function AdminRouteFallback() {
  const { t } = useTranslation()
  return (
    <div className="admin-card">
      {t('admin.auth.checking')}
    </div>
  )
}

function AuthGate({
  children,
}: {
  children: ReactNode
}) {
  const { t } = useTranslation()
  const status = useAdminAuth((s) => s.status)
  const setStatus = useAdminAuth(
    (s) => s.setStatus,
  )
  const setSession = useAdminAuth(
    (s) => s.setSession,
  )
  const setCapabilities = useAdminAuth(
    (s) => s.setCapabilities,
  )
  const restorePendingDevice = useAdminAuth(
    (s) => s.restorePendingDevice,
  )

  useEffect(() => {
    setUserTokenProvider(() => api.getToken())
  }, [])

  useEffect(() => {
    if (status !== 'loading') return

    let active = true

    const csrfPromise = adminApi
      .ensureCsrf()
      .catch(() => {
        // tolerate failure — we'll get one on next mutating call
      })
    const metaPromise = adminApi.bootstrapMetadata()

    Promise.allSettled([
      csrfPromise,
      metaPromise,
    ]).then(async ([_csrf, metaRes]) => {
      if (!active) return
      if (metaRes.status !== 'fulfilled') {
        clearDeviceApprovalBrowserState()
        setStatus('unauth')
        return
      }
      const meta = metaRes.value
      if (!meta.is_admin) {
        clearDeviceApprovalBrowserState()
        setStatus('unauth')
        return
      }
      if (!meta.admin_init) {
        setStatus('needs_init')
        return
      }
      try {
        const refreshed = await adminApi.refresh()
        if (!active) return
        setSession(
          refreshed.access_token,
          refreshed.expires_in,
        )
        try {
          const manifest =
            await api.getAdminManifest()
          if (active) {
            setCapabilities(
              manifest.capabilities ?? [],
            )
          }
        } catch {
          /* manifest is optional for auth */
        }
      } catch {
        if (!active) return
        const pendingId = readPendingDeviceId()
        if (pendingId !== null) {
          restorePendingDevice(pendingId)
        } else {
          setStatus('needs_login')
        }
      }
    })

    return () => {
      active = false
    }
  }, [
    status,
    setStatus,
    setSession,
    setCapabilities,
    restorePendingDevice,
  ])

  if (status === 'loading') {
    return (
      <div className="admin-auth-screen adm-r-auth-stage">
        <div className="admin-auth-card">
          {t('admin.auth.checking')}
        </div>
      </div>
    )
  }
  if (status === 'unauth') {
    return (
      <div className="admin-auth-screen adm-r-auth-stage">
        <div className="admin-auth-card">
          <h2>{t('admin.auth.adminOnly')}</h2>
          <p>{t('admin.auth.adminOnlyHint')}</p>
        </div>
      </div>
    )
  }
  if (status === 'needs_init') {
    return (
      <Suspense fallback={<AdminChunkFallback />}>
        <div className="admin-auth-screen adm-r-auth-stage">
          <AdminInit />
        </div>
      </Suspense>
    )
  }
  if (status === 'needs_login') {
    return (
      <Suspense fallback={<AdminChunkFallback />}>
        <div className="admin-auth-screen adm-r-auth-stage">
          <AdminLogin />
        </div>
      </Suspense>
    )
  }
  if (status === 'needs_device_approval') {
    return (
      <Suspense fallback={<AdminChunkFallback />}>
        <div className="admin-auth-screen adm-r-auth-stage">
          <DeviceApproval />
        </div>
      </Suspense>
    )
  }
  return <>{children}</>
}

export function AdminApp() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthGate>
        <StepUpProvider>
          <AdminPromptProvider>
            {/* Mounted under outer admin route, so child
             * paths remain relative to that prefix. */}
            <Suspense fallback={<AdminRouteFallback />}>
              <Routes>
                <Route element={<AdminShell />}>
                  <Route
                    index
                    element={<DashboardRoute />}
                  />
                  <Route
                    path="users"
                    element={<UsersRoute />}
                  />
                  <Route
                    path="tracks"
                    element={<TracksRoute />}
                  />
                  <Route
                    path="albums"
                    element={<AlbumsListRoute />}
                  />
                  <Route
                    path="albums/:albumId"
                    element={<AlbumDetailRoute />}
                  />
                  <Route
                    path="playlists"
                    element={<PlaylistsListRoute />}
                  />
                  <Route
                    path="playlists/:playlistId"
                    element={<PlaylistDetailRoute />}
                  />
                  <Route
                    path="complaints"
                    element={<ComplaintsRoute />}
                  />
                  <Route
                    path="artists/station-gap"
                    element={<StationGapRoute />}
                  />
                  <Route
                    path="artists"
                    element={<ArtistsRoute />}
                  />
                  <Route
                    path="audio-compute"
                    element={<AudioComputeRoute />}
                  />
                  <Route
                    path="tasks"
                    element={<TasksRoute />}
                  />
                  <Route
                    path="schedules"
                    element={<SchedulesRoute />}
                  />
                  <Route
                    path="logs"
                    element={<LogsRoute />}
                  />
                  <Route
                    path="metrics"
                    element={<MetricsRoute />}
                  />
                  <Route
                    path="network"
                    element={<NetworkRoute />}
                  />
                  <Route
                    path="containers"
                    element={<ContainersRoute />}
                  />
                  <Route
                    path="audit"
                    element={<AuditRoute />}
                  />
                  <Route
                    path="security"
                    element={<SecurityRoute />}
                  />
                  <Route
                    path="settings"
                    element={<SettingsRoute />}
                  />
                  <Route
                    path="recsys"
                    element={<RecsysRoute />}
                  />
                  <Route
                    path="antivirus"
                    element={<AntivirusRoute />}
                  />
                  <Route
                    path="profile"
                    element={<AdminProfileRoute />}
                  />
                </Route>
              </Routes>
            </Suspense>
          </AdminPromptProvider>
        </StepUpProvider>
      </AuthGate>
    </QueryClientProvider>
  )
}

export default AdminApp
