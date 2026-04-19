import { useQuery } from '@tanstack/react-query'
import { adminApi } from '../lib/adminApi'
import { KpiCard } from '../components/widgets/KpiCard'
import { StatusPill } from '../components/widgets/StatusPill'

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let n = bytes
  let i = 0
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024
    i += 1
  }
  return `${n.toFixed(1)} ${units[i]}`
}

export function DashboardRoute() {
  const { data, error, isLoading } = useQuery({
    queryKey: ['admin', 'dashboard', 'overview'],
    queryFn: () => adminApi.dashboardOverview(),
    refetchInterval: 10_000,
  })
  const containers = useQuery({
    queryKey: ['admin', 'containers', 'overview'],
    queryFn: () => adminApi.containers(),
    refetchInterval: 10_000,
  })

  if (isLoading) {
    return <div>Loading dashboard…</div>
  }
  if (error) {
    return (
      <div className="admin-error">
        Failed: {(error as Error).message}
      </div>
    )
  }
  if (!data) return null
  const containerCounts =
    containers.data?.counts || {
      ok: 0,
      warning: 0,
      error: 0,
      unknown: 0,
    }
  const total = containers.data?.total || 0
  return (
    <div className="admin-dashboard">
      <h1>Dashboard</h1>
      <section className="kpi-grid">
        <KpiCard
          label="Online now"
          value={data.users.online_now}
          hint={`${data.users.active} active accounts`}
        />
        <KpiCard
          label="Users (total)"
          value={data.users.total}
          hint={`${data.users.new_24h} new in 24h`}
        />
        <KpiCard
          label="Tracks"
          value={data.tracks.total}
          hint={`${data.tracks.new_24h} new in 24h`}
        />
        <KpiCard
          label="Storage"
          value={formatBytes(
            data.tracks.storage_bytes,
          )}
        />
        <KpiCard
          label="Open complaints"
          value={data.complaints.open}
          accent={
            data.complaints.open > 0
              ? 'warn'
              : 'default'
          }
        />
        <KpiCard
          label="Active jobs"
          value={data.jobs.active}
          hint={
            data.jobs.failed_1h
              ? `${data.jobs.failed_1h} failed (1h)`
              : 'no failures'
          }
          accent={
            data.jobs.failed_1h > 0
              ? 'warn'
              : 'default'
          }
        />
      </section>
      <section className="admin-card">
        <h2>Containers</h2>
        <p className="admin-card__sub">
          {total} containers tracked
        </p>
        <div className="status-row">
          <StatusPill kind="ok">
            healthy {containerCounts.ok}
          </StatusPill>
          <StatusPill kind="warn">
            warning {containerCounts.warning}
          </StatusPill>
          <StatusPill kind="error">
            error {containerCounts.error}
          </StatusPill>
          <StatusPill kind="unknown">
            unknown {containerCounts.unknown}
          </StatusPill>
        </div>
      </section>
    </div>
  )
}
