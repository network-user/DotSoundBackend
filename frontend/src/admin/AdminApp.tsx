import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'
import { Route, Routes } from 'react-router-dom'
import { api } from '@/lib/api'
import { AdminInit } from './components/auth/AdminInit'
import { AdminLogin } from './components/auth/AdminLogin'
import { DeviceApproval } from './components/auth/DeviceApproval'
import { StepUpProvider } from './components/auth/StepUpDialog'
import { AdminPromptProvider } from './components/layout/AdminPromptContext'
import { AdminShell } from './components/layout/AdminShell'
import { adminApi } from './lib/adminApi'
import { setUserTokenProvider } from './lib/adminApi'
import { useAdminAuth } from './store/adminAuthStore'
import { ArtistsRoute } from './routes/ArtistsRoute'
import { AuditRoute } from './routes/AuditRoute'
import { AudioComputeRoute } from './routes/AudioComputeRoute'
import { ComplaintsRoute } from './routes/ComplaintsRoute'
import { ContainersRoute } from './routes/ContainersRoute'
import { DashboardRoute } from './routes/DashboardRoute'
import { LogsRoute } from './routes/LogsRoute'
import { MetricsRoute } from './routes/MetricsRoute'
import { SecurityRoute } from './routes/SecurityRoute'
import { SettingsRoute } from './routes/SettingsRoute'
import { SchedulesRoute } from './routes/SchedulesRoute'
import { TasksRoute } from './routes/TasksRoute'
import { AlbumDetailRoute } from './routes/AlbumDetailRoute'
import { AlbumsListRoute } from './routes/AlbumsListRoute'
import { PlaylistDetailRoute } from './routes/PlaylistDetailRoute'
import { PlaylistsListRoute } from './routes/PlaylistsListRoute'
import { TracksRoute } from './routes/TracksRoute'
import { UsersRoute } from './routes/UsersRoute'
import '@/styles/admin/redesign-admin.css'
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

function AuthGate({
  children,
}: {
  children: React.ReactNode
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
        setStatus('unauth')
        return
      }
      const meta = metaRes.value
      if (!meta.is_admin) {
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
        if (active) setStatus('needs_login')
      }
    })

    return () => {
      active = false
    }
  }, [status, setStatus, setSession, setCapabilities])

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
      <div className="admin-auth-screen adm-r-auth-stage">
        <AdminInit />
      </div>
    )
  }
  if (status === 'needs_login') {
    return (
      <div className="admin-auth-screen adm-r-auth-stage">
        <AdminLogin />
      </div>
    )
  }
  if (status === 'needs_device_approval') {
    return (
      <div className="admin-auth-screen adm-r-auth-stage">
        <DeviceApproval />
      </div>
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
            {/* Mounted under outer <Route path="/admin/*">,
             * so paths below are relative to /admin. */}
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
              </Route>
            </Routes>
          </AdminPromptProvider>
        </StepUpProvider>
      </AuthGate>
    </QueryClientProvider>
  )
}

export default AdminApp
