import { useTranslation } from 'react-i18next'
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { adminApi } from '../lib/adminApi'
import { KpiCard } from '../components/widgets/KpiCard'
import { StatusPill } from '../components/widgets/StatusPill'
import {
  ChartPoint,
  LineChart,
} from '../components/charts/LineChart'

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

interface PromRange {
  data?: {
    result?: Array<{
      values: Array<[number, string]>
    }>
  }
}

function flattenRange(raw: unknown): ChartPoint[] {
  const data = raw as PromRange
  const points = data?.data?.result?.[0]?.values
  if (!points) return []
  return points.map(([ts, value]) => ({
    ts,
    value: Number(value),
  }))
}

function calcTrend(points: ChartPoint[]): number {
  if (points.length < 2) return 0
  const first = points[0]?.value ?? 0
  const last = points[points.length - 1]?.value ?? 0
  if (first === 0) return last > 0 ? 100 : 0
  return ((last - first) / first) * 100
}

export function DashboardRoute() {
  const { t } = useTranslation()
  const [minutes, setMinutes] = useState(60)
  const [live, setLive] = useState(true)

  const { data, error, isLoading } = useQuery({
    queryKey: ['admin', 'dashboard', 'overview'],
    queryFn: () => adminApi.dashboardOverview(),
    refetchInterval: live ? 30_000 : false,
    refetchIntervalInBackground: false,
  })
  const containers = useQuery({
    queryKey: ['admin', 'containers', 'overview'],
    queryFn: () => adminApi.containers(),
    refetchInterval: live ? 30_000 : false,
    refetchIntervalInBackground: false,
  })
  const onlineHistory = useQuery({
    queryKey: ['admin', 'dashboard', 'online', minutes],
    queryFn: () =>
      adminApi.dashboardTimeseries(
        'active_websockets',
        minutes,
        30,
      ),
    refetchInterval: live ? 30_000 : false,
    refetchIntervalInBackground: false,
  })
  const rpsHistory = useQuery({
    queryKey: ['admin', 'dashboard', 'rps', minutes],
    queryFn: () =>
      adminApi.dashboardTimeseries('rps_5m', minutes, 30),
    refetchInterval: live ? 30_000 : false,
    refetchIntervalInBackground: false,
  })
  const latencyHistory = useQuery({
    queryKey: ['admin', 'dashboard', 'latency', minutes],
    queryFn: () =>
      adminApi.dashboardTimeseries(
        'latency_p95_5m',
        minutes,
        30,
      ),
    refetchInterval: live ? 30_000 : false,
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
  const onlinePoints = flattenRange(onlineHistory.data)
  const rpsPoints = flattenRange(rpsHistory.data)
  const latencyPoints = flattenRange(latencyHistory.data)
  const onlineTrend = useMemo(
    () => calcTrend(onlinePoints),
    [onlinePoints],
  )
  const trendClass =
    onlineTrend > 2
      ? 'up'
      : onlineTrend < -2
        ? 'down'
        : 'flat'

  return (
    <div className="admin-dashboard">
      <h1>{t('admin.dashboard.title')}</h1>
      <section className="admin-card admin-dashboard__hero">
        <div>
          <h2>{t('admin.dashboard.onlineHistory.title')}</h2>
          <p className="admin-card__sub">
            {t('admin.dashboard.onlineHistory.subtitle')}
          </p>
        </div>
        <div className="admin-range-switch" role="tablist">
          {[15, 60, 360, 1440].map((value) => (
            <button
              key={value}
              type="button"
              className={`admin-range-switch__btn${
                value === minutes ? ' is-active' : ''
              }`}
              onClick={() => setMinutes(value)}
            >
              {value < 60
                ? `${value}m`
                : value < 1440
                  ? `${Math.floor(value / 60)}h`
                  : '24h'}
            </button>
          ))}
          <button
            type="button"
            className={`admin-range-switch__btn${
              live ? ' is-active' : ''
            }`}
            onClick={() => setLive((v) => !v)}
          >
            Live
          </button>
        </div>
      </section>

      <section className="admin-card">
        <div className="admin-dashboard__chart-head">
          <h2>{t('admin.dashboard.onlineHistory.chartTitle')}</h2>
          <span
            className={`admin-dashboard__trend admin-dashboard__trend--${trendClass}`}
          >
            {onlineTrend > 0 ? '+' : ''}
            {onlineTrend.toFixed(1)}%
          </span>
        </div>
        {onlineHistory.isLoading ? (
          <div className="admin-skeleton admin-skeleton--card" />
        ) : onlinePoints.length > 0 ? (
          <LineChart
            data={onlinePoints}
            ariaLabel={t(
              'admin.dashboard.onlineHistory.chartTitle',
            )}
          />
        ) : (
          <div className="admin-log-empty">
            No online data for selected range
          </div>
        )}
      </section>

      <section className="kpi-grid">
        <KpiCard
          label={t(
            'admin.dashboard.kpi.onlineNow',
          )}
          value={data.users.online_now}
          hint={
            <>
              {t(
                'admin.dashboard.kpi.activeAccounts',
                { count: data.users.active },
              )}
              <span
                className={`admin-kpi-trend admin-kpi-trend--${trendClass}`}
              >
                {onlineTrend > 0 ? '+' : ''}
                {onlineTrend.toFixed(1)}%
              </span>
            </>
          }
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

      <section className="kpi-grid kpi-grid--charts">
        <article className="admin-card">
          <h2>{t('admin.dashboard.charts.rps')}</h2>
          <LineChart
            data={rpsPoints}
            height={180}
            ariaLabel={t('admin.dashboard.charts.rps')}
          />
        </article>
        <article className="admin-card">
          <h2>{t('admin.dashboard.charts.latency')}</h2>
          <LineChart
            data={latencyPoints}
            height={180}
            ariaLabel={t('admin.dashboard.charts.latency')}
          />
        </article>
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
