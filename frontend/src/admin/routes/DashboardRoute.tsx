import { useTranslation } from 'react-i18next'
import { useEffect, useMemo, useState } from 'react'
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
  const [onlineRangeMode, setOnlineRangeMode] = useState<
    'range' | 'all'
  >('range')
  const [onlineSortDir, setOnlineSortDir] = useState<
    'asc' | 'desc'
  >('asc')
  const [live, setLive] = useState(true)
  const [statsPeriod, setStatsPeriod] = useState<
    'today' | '7d' | '30d' | 'all'
  >('today')
  const [statsMetric, setStatsMetric] = useState<
    | 'all'
    | 'users_registered'
    | 'listens_total'
    | 'unique_listeners'
    | 'tracks_uploaded'
    | 'completed_listens'
    | 'skips'
  >('all')
  const metricOptions: Array<{
    value:
      | 'all'
      | 'users_registered'
      | 'listens_total'
      | 'unique_listeners'
      | 'tracks_uploaded'
      | 'completed_listens'
      | 'skips'
    label: string
  }> = [
    { value: 'all', label: t('admin.dashboard.stats.filterAll') },
    {
      value: 'users_registered',
      label: t('admin.dashboard.stats.usersRegistered'),
    },
    {
      value: 'listens_total',
      label: t('admin.dashboard.stats.listensTotal'),
    },
    {
      value: 'unique_listeners',
      label: t('admin.dashboard.stats.uniqueListeners'),
    },
    {
      value: 'tracks_uploaded',
      label: t('admin.dashboard.stats.tracksUploaded'),
    },
    {
      value: 'completed_listens',
      label: t('admin.dashboard.stats.completed'),
    },
    { value: 'skips', label: t('admin.dashboard.stats.skips') },
  ]
  const metricIndex = Math.max(
    0,
    metricOptions.findIndex((opt) => opt.value === statsMetric),
  )
  const [topSortBy, setTopSortBy] = useState<
    'plays' | 'unique_listeners'
  >('plays')
  const [topSortDir, setTopSortDir] = useState<
    'desc' | 'asc'
  >('desc')
  const [onlineFallback, setOnlineFallback] = useState<
    ChartPoint[]
  >([])

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
  const stats = useQuery({
    queryKey: ['admin', 'dashboard', 'stats', statsPeriod],
    queryFn: () => adminApi.dashboardStats(statsPeriod),
    refetchInterval: live ? 30_000 : false,
    refetchIntervalInBackground: false,
  })
  const activation = useQuery({
    queryKey: ['admin', 'dashboard', 'activation', statsPeriod],
    queryFn: () => adminApi.dashboardActivationFunnel(statsPeriod),
    refetchInterval: live ? 30_000 : false,
    refetchIntervalInBackground: false,
  })
  useEffect(() => {
    if (!data?.generated_at) return
    setOnlineFallback((prev) => {
      const next = [
        ...prev,
        { ts: data.generated_at, value: data.users.online_now },
      ]
      return next.slice(-120)
    })
  }, [data?.generated_at, data?.users.online_now])

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
  const baseOnlinePoints =
    onlinePoints.length > 0 ? onlinePoints : onlineFallback
  const displayOnlinePoints = useMemo(() => {
    const source =
      onlineRangeMode === 'all'
        ? onlineFallback
        : baseOnlinePoints
    const sorted = [...source].sort((a, b) =>
      onlineSortDir === 'asc' ? a.ts - b.ts : b.ts - a.ts,
    )
    return sorted
  }, [
    onlineRangeMode,
    onlineFallback,
    baseOnlinePoints,
    onlineSortDir,
  ])
  const onlineTrend = useMemo(
    () => calcTrend(displayOnlinePoints),
    [displayOnlinePoints],
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
              onlineRangeMode === 'all' ? ' is-active' : ''
            }`}
            onClick={() => setOnlineRangeMode('all')}
          >
            All-time
          </button>
          <button
            type="button"
            className={`admin-range-switch__btn${
              onlineRangeMode === 'range'
                ? ' is-active'
                : ''
            }`}
            onClick={() => setOnlineRangeMode('range')}
          >
            Interval
          </button>
          <button
            type="button"
            className="admin-range-switch__btn"
            onClick={() =>
              setOnlineSortDir((v) =>
                v === 'asc' ? 'desc' : 'asc',
              )
            }
          >
            {onlineSortDir === 'asc'
              ? 'Oldest first'
              : 'Newest first'}
          </button>
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
        ) : displayOnlinePoints.length > 0 ? (
          <LineChart
            data={displayOnlinePoints}
            ariaLabel={t(
              'admin.dashboard.onlineHistory.chartTitle',
            )}
          />
        ) : (
          <div className="admin-log-empty">
            No online data yet
          </div>
        )}
      </section>

      <section className="admin-card">
        <div className="admin-dashboard__hero">
          <div>
            <h2>{t('admin.dashboard.stats.title')}</h2>
            <p className="admin-card__sub">
              {t('admin.dashboard.stats.subtitle')}
            </p>
          </div>
          <div className="admin-range-switch" role="tablist">
            {(['today', '7d', '30d', 'all'] as const).map((value) => (
              <button
                key={value}
                type="button"
                className={`admin-range-switch__btn${
                  statsPeriod === value ? ' is-active' : ''
                }`}
                onClick={() => setStatsPeriod(value)}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
        {stats.isLoading || !stats.data ? (
          <div className="admin-skeleton admin-skeleton--card" />
        ) : (
          <>
            <div className="admin-metric-slider">
              <div className="admin-metric-slider__label">
                {metricOptions[metricIndex]?.label}
              </div>
              <input
                className="admin-metric-slider__input"
                type="range"
                min={0}
                max={metricOptions.length - 1}
                step={1}
                value={metricIndex}
                onChange={(e) => {
                  const idx = Number(e.target.value)
                  const option = metricOptions[idx]
                  if (option) setStatsMetric(option.value)
                }}
                aria-label="Select statistics metric"
              />
              <div className="admin-metric-slider__ticks">
                {metricOptions.map((opt, idx) => (
                  <button
                    key={opt.value}
                    type="button"
                    className={`admin-metric-slider__tick${
                      idx === metricIndex ? ' is-active' : ''
                    }`}
                    onClick={() => setStatsMetric(opt.value)}
                    aria-label={opt.label}
                  />
                ))}
              </div>
            </div>
            {statsMetric === 'all' && (
              <section className="kpi-grid">
              {(statsMetric === 'all' || statsMetric === 'users_registered') && (
                <KpiCard
                  label={t('admin.dashboard.stats.usersRegistered')}
                  value={stats.data.users_registered}
                />
              )}
              {(statsMetric === 'all' ||
                statsMetric === 'listens_total') && (
                <KpiCard
                  label={t('admin.dashboard.stats.listensTotal')}
                  value={stats.data.listens_total}
                />
              )}
              {(statsMetric === 'all' ||
                statsMetric === 'unique_listeners') && (
                <KpiCard
                  label={t('admin.dashboard.stats.uniqueListeners')}
                  value={stats.data.unique_listeners}
                />
              )}
              {(statsMetric === 'all' ||
                statsMetric === 'tracks_uploaded') && (
                <KpiCard
                  label={t('admin.dashboard.stats.tracksUploaded')}
                  value={stats.data.tracks_uploaded}
                />
              )}
              {(statsMetric === 'all' ||
                statsMetric === 'completed_listens') && (
                <KpiCard
                  label={t('admin.dashboard.stats.completed')}
                  value={stats.data.completed_listens}
                />
              )}
              {(statsMetric === 'all' ||
                statsMetric === 'skips') && (
                <KpiCard
                  label={t('admin.dashboard.stats.skips')}
                  value={stats.data.skips}
                  accent={stats.data.skips > 0 ? 'warn' : 'default'}
                />
              )}
              </section>
            )}
            {statsMetric !== 'all' && (
              <div
                key={statsMetric}
                className="admin-metric-focus"
              >
                {statsMetric === 'users_registered' && (
                  <KpiCard
                    label={t('admin.dashboard.stats.usersRegistered')}
                    value={stats.data.users_registered}
                  />
                )}
                {statsMetric === 'listens_total' && (
                  <KpiCard
                    label={t('admin.dashboard.stats.listensTotal')}
                    value={stats.data.listens_total}
                  />
                )}
                {statsMetric === 'unique_listeners' && (
                  <KpiCard
                    label={t('admin.dashboard.stats.uniqueListeners')}
                    value={stats.data.unique_listeners}
                  />
                )}
                {statsMetric === 'tracks_uploaded' && (
                  <KpiCard
                    label={t('admin.dashboard.stats.tracksUploaded')}
                    value={stats.data.tracks_uploaded}
                  />
                )}
                {statsMetric === 'completed_listens' && (
                  <KpiCard
                    label={t('admin.dashboard.stats.completed')}
                    value={stats.data.completed_listens}
                  />
                )}
                {statsMetric === 'skips' && (
                  <KpiCard
                    label={t('admin.dashboard.stats.skips')}
                    value={stats.data.skips}
                    accent={stats.data.skips > 0 ? 'warn' : 'default'}
                  />
                )}
              </div>
            )}
            <div className="admin-card admin-dashboard__toplist">
              <div className="admin-dashboard__toplist-head">
                <h3>{t('admin.dashboard.stats.topTracks')}</h3>
                <div className="admin-range-switch">
                  <button
                    type="button"
                    className={`admin-range-switch__btn${
                      topSortBy === 'plays' ? ' is-active' : ''
                    }`}
                    onClick={() => setTopSortBy('plays')}
                  >
                    Plays
                  </button>
                  <button
                    type="button"
                    className={`admin-range-switch__btn${
                      topSortBy === 'unique_listeners'
                        ? ' is-active'
                        : ''
                    }`}
                    onClick={() =>
                      setTopSortBy('unique_listeners')
                    }
                  >
                    Listeners
                  </button>
                  <button
                    type="button"
                    className="admin-range-switch__btn"
                    onClick={() =>
                      setTopSortDir((v) =>
                        v === 'desc' ? 'asc' : 'desc',
                      )
                    }
                  >
                    {topSortDir === 'desc' ? 'Desc' : 'Asc'}
                  </button>
                </div>
              </div>
              {stats.data.top_tracks.length === 0 ? (
                <div className="admin-log-empty">
                  {t('admin.dashboard.stats.noData')}
                </div>
              ) : (
                <div className="admin-dashboard__toplist-rows">
                  {[...stats.data.top_tracks]
                    .sort((a, b) => {
                      const left =
                        topSortBy === 'plays'
                          ? a.plays
                          : a.unique_listeners
                      const right =
                        topSortBy === 'plays'
                          ? b.plays
                          : b.unique_listeners
                      return topSortDir === 'desc'
                        ? right - left
                        : left - right
                    })
                    .map((item) => (
                    <div
                      key={item.track_id}
                      className="admin-dashboard__toplist-row"
                    >
                      <div className="admin-dashboard__toplist-title">
                        {item.title}
                      </div>
                      <div className="admin-dashboard__toplist-meta">
                        {item.plays} plays · {item.unique_listeners} listeners
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </section>

      <section className="kpi-grid">
        {activation.data && (
          <>
            <KpiCard
              label="Auth -> First Play (sec)"
              value={activation.data.avg_auth_to_first_play_seconds}
            />
            <KpiCard
              label="Onboarding Completion Rate"
              value={
                activation.data.users.auth_success
                  ? `${Math.round(
                      (activation.data.users.onboarding_complete /
                        activation.data.users.auth_success) *
                        100,
                    )}%`
                  : '0%'
              }
            />
            <KpiCard
              label="Skip Onboarding Rate"
              value={`${Math.round(activation.data.skip_rate * 100)}%`}
              accent={
                activation.data.skip_rate > 0.4 ? 'warn' : 'default'
              }
            />
            <KpiCard
              label="First Session Plays"
              value={activation.data.first_session_plays_count}
            />
          </>
        )}
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
