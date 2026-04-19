import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation()
  const { data, error, isLoading } = useQuery({
    queryKey: ['admin', 'dashboard', 'overview'],
    queryFn: () => adminApi.dashboardOverview(),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })
  const containers = useQuery({
    queryKey: ['admin', 'containers', 'overview'],
    queryFn: () => adminApi.containers(),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })

  if (isLoading) {
    return <div>{t('admin.dashboard.loading')}</div>
  }
  if (error) {
    return (
      <div className="admin-error">
        {t('admin.dashboard.loadFailed')}:{' '}
        {(error as Error).message}
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
      <h1>{t('admin.dashboard.title')}</h1>
      <section className="kpi-grid">
        <KpiCard
          label={t(
            'admin.dashboard.kpi.onlineNow',
          )}
          value={data.users.online_now}
          hint={t(
            'admin.dashboard.kpi.activeAccounts',
            { count: data.users.active },
          )}
        />
        <KpiCard
          label={t(
            'admin.dashboard.kpi.usersTotal',
          )}
          value={data.users.total}
          hint={t(
            'admin.dashboard.kpi.newIn24h',
            { count: data.users.new_24h },
          )}
        />
        <KpiCard
          label={t('admin.dashboard.kpi.tracks')}
          value={data.tracks.total}
          hint={t(
            'admin.dashboard.kpi.newIn24h',
            { count: data.tracks.new_24h },
          )}
        />
        <KpiCard
          label={t('admin.dashboard.kpi.storage')}
          value={formatBytes(
            data.tracks.storage_bytes,
          )}
        />
        <KpiCard
          label={t(
            'admin.dashboard.kpi.openComplaints',
          )}
          value={data.complaints.open}
          accent={
            data.complaints.open > 0
              ? 'warn'
              : 'default'
          }
        />
        <KpiCard
          label={t(
            'admin.dashboard.kpi.activeJobs',
          )}
          value={data.jobs.active}
          hint={
            data.jobs.failed_1h
              ? t(
                  'admin.dashboard.kpi.failedIn1h',
                  { count: data.jobs.failed_1h },
                )
              : t('admin.dashboard.kpi.noFailures')
          }
          accent={
            data.jobs.failed_1h > 0
              ? 'warn'
              : 'default'
          }
        />
      </section>
      <section className="admin-card">
        <h2>{t('admin.dashboard.containers.title')}</h2>
        <p className="admin-card__sub">
          {t(
            'admin.dashboard.containers.tracked',
            { count: total },
          )}
        </p>
        <div className="status-row">
          <StatusPill kind="ok">
            {t(
              'admin.dashboard.containers.healthy',
              { count: containerCounts.ok },
            )}
          </StatusPill>
          <StatusPill kind="warn">
            {t(
              'admin.dashboard.containers.warning',
              { count: containerCounts.warning },
            )}
          </StatusPill>
          <StatusPill kind="error">
            {t(
              'admin.dashboard.containers.error',
              { count: containerCounts.error },
            )}
          </StatusPill>
          <StatusPill kind="unknown">
            {t(
              'admin.dashboard.containers.unknown',
              { count: containerCounts.unknown },
            )}
          </StatusPill>
        </div>
      </section>
    </div>
  )
}
