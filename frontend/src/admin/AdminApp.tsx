import { useEffect } from 'react'
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
import { AdminShell } from './components/layout/AdminShell'
import { adminApi } from './lib/adminApi'
import { setUserTokenProvider } from './lib/adminApi'
import { useAdminAuth } from './store/adminAuthStore'
import { AuditRoute } from './routes/AuditRoute'
import { ComplaintsRoute } from './routes/ComplaintsRoute'
import { ContainersRoute } from './routes/ContainersRoute'
import { DashboardRoute } from './routes/DashboardRoute'
import { LogsRoute } from './routes/LogsRoute'
import { MetricsRoute } from './routes/MetricsRoute'
import { SecurityRoute } from './routes/SecurityRoute'
import { SettingsRoute } from './routes/SettingsRoute'
import { TasksRoute } from './routes/TasksRoute'
import { TracksRoute } from './routes/TracksRoute'
import { UsersRoute } from './routes/UsersRoute'
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
  const status = useAdminAuth((s) => s.status)
  const setStatus = useAdminAuth(
    (s) => s.setStatus,
  )

  useEffect(() => {
    setUserTokenProvider(() => api.getToken())
  }, [])

  useEffect(() => {
    let cancelled = false
    if (status !== 'loading') return
    adminApi
      .ensureCsrf()
      .catch(() => {
        // tolerate failure — we'll get one on next mutating call
      })
      .then(() => adminApi.bootstrapMetadata())
      .then((meta) => {
        if (cancelled) return
        if (!meta.is_admin) {
          setStatus('unauth')
          return
        }
        if (!meta.admin_init) {
          setStatus('needs_init')
          return
        }
        setStatus('needs_login')
      })
      .catch(() => {
        if (!cancelled) setStatus('unauth')
      })
    return () => {
      cancelled = true
    }
  }, [status, setStatus])

  if (status === 'loading') {
    return (
      <div className="admin-auth-screen">
        <div className="admin-auth-card">
          Checking session…
        </div>
      </div>
    )
  }
  if (status === 'unauth') {
    return (
      <div className="admin-auth-screen">
        <div className="admin-auth-card">
          <h2>Admin only</h2>
          <p>
            This area is for accounts with the
            admin flag. Sign in to your account
            first, then return here.
          </p>
        </div>
      </div>
    )
  }
  if (status === 'needs_init') {
    return (
      <div className="admin-auth-screen">
        <AdminInit />
      </div>
    )
  }
  if (status === 'needs_login') {
    return (
      <div className="admin-auth-screen">
        <AdminLogin />
      </div>
    )
  }
  if (status === 'needs_device_approval') {
    return (
      <div className="admin-auth-screen">
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
          <AdminShell>
            <Routes>
              <Route
                path="/admin"
                element={<DashboardRoute />}
              />
              <Route
                path="/admin/users"
                element={<UsersRoute />}
              />
              <Route
                path="/admin/tracks"
                element={<TracksRoute />}
              />
              <Route
                path="/admin/complaints"
                element={<ComplaintsRoute />}
              />
              <Route
                path="/admin/tasks"
                element={<TasksRoute />}
              />
              <Route
                path="/admin/logs"
                element={<LogsRoute />}
              />
              <Route
                path="/admin/metrics"
                element={<MetricsRoute />}
              />
              <Route
                path="/admin/containers"
                element={<ContainersRoute />}
              />
              <Route
                path="/admin/audit"
                element={<AuditRoute />}
              />
              <Route
                path="/admin/security"
                element={<SecurityRoute />}
              />
              <Route
                path="/admin/settings"
                element={<SettingsRoute />}
              />
            </Routes>
          </AdminShell>
        </StepUpProvider>
      </AuthGate>
    </QueryClientProvider>
  )
}

export default AdminApp
