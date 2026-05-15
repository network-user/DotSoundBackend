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
import type { Variants } from 'framer-motion'
import {
  m,
  VARIANTS_FADE_UP,
} from '@/lib/motion'
import { MotionPress } from '@/components/ui/MotionPress'
import { AdminRangeSwitch } from '../components/widgets/AdminRangeSwitch'
import { OutboundStatusPanel } from '../components/widgets/OutboundStatusPanel'

const ADMIN_DASH_KPI_STAGGER: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.06 },
  },
}

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

function formatPercent(
  value: number | null | undefined,
): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'n/a'
  }
  return `${value.toFixed(1)}%`
}

function resourceAccent(
  value: number | null | undefined,
): 'default' | 'warn' | 'error' {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'default'
  }
  if (value >= 90) return 'error'
  if (value >= 75) return 'warn'
  return 'default'
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
  const [topSortBy, setTopSortBy] = useState<
    'plays' | 'unique_listeners'
  >('plays')
  const [topSortDir, setTopSortDir] = useState<
    'desc' | 'asc'
  >('desc')
  const [onlineFallback, setOnlineFallback] = useState<
    ChartPoint[]
  >([])
  const radioSkipDays =
    statsPeriod === 'today'
      ? 1
      : statsPeriod === '7d'
        ? 7
        : 30

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
  const systemResources = useQuery({
    queryKey: ['admin', 'dashboard', 'system-resources', minutes],
    queryFn: () => adminApi.systemResources(minutes),
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
  const radioReqHistory = useQuery({
    queryKey: ['admin', 'dashboard', 'radio-req', minutes],
    queryFn: () =>
      adminApi.dashboardTimeseries(
        'radio_requests_5m',
        minutes,
        30,
      ),
    refetchInterval: live ? 30_000 : false,
    refetchIntervalInBackground: false,
  })
  const radioGuardHistory = useQuery({
    queryKey: ['admin', 'dashboard', 'radio-guard', minutes],
    queryFn: () =>
      adminApi.dashboardTimeseries(
        'radio_guard_hits_5m',
        minutes,
        30,
      ),
    refetchInterval: live ? 30_000 : false,
    refetchIntervalInBackground: false,
  })
  const radioQueueSizeHistory = useQuery({
    queryKey: ['admin', 'dashboard', 'radio-queue-size', minutes],
    queryFn: () =>
      adminApi.dashboardTimeseries(
        'radio_queue_size_avg_5m',
        minutes,
        30,
      ),
    refetchInterval: live ? 30_000 : false,
    refetchIntervalInBackground: false,
  })
  const radioSkipReasons = useQuery({
    queryKey: [
      'admin',
      'dashboard',
      'radio-auto-skip-reasons',
      radioSkipDays,
    ],
    queryFn: () =>
      adminApi.dashboardRadioAutoSkipReasons(radioSkipDays, 10),
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

  const onlinePoints = flattenRange(
    onlineHistory.data,
  )
  const rpsPoints = flattenRange(rpsHistory.data)
  const latencyPoints = flattenRange(
    latencyHistory.data,
  )
  const radioReqPoints = flattenRange(radioReqHistory.data)
  const radioGuardPoints = flattenRange(
    radioGuardHistory.data,
  )
  const radioQueueSizePoints = flattenRange(
    radioQueueSizeHistory.data,
  )
  const resourceHistory =
    systemResources.data?.history ?? []
  const cpuPoints: ChartPoint[] = resourceHistory
    .filter((item) => typeof item.cpu_pct === 'number')
    .map((item) => ({
      ts: item.ts,
      value: item.cpu_pct ?? 0,
    }))
  const memoryPoints: ChartPoint[] = resourceHistory
    .filter(
      (item) => typeof item.memory_used_pct === 'number',
    )
    .map((item) => ({
      ts: item.ts,
      value: item.memory_used_pct ?? 0,
    }))
  const storagePoints: ChartPoint[] = resourceHistory
    .filter(
      (item) => typeof item.storage_used_pct === 'number',
    )
    .map((item) => ({
      ts: item.ts,
      value: item.storage_used_pct ?? 0,
    }))
  const currentResources = systemResources.data?.current
  const latestRadioReq = radioReqPoints.at(-1)?.value ?? 0
  const latestRadioGuard =
    radioGuardPoints.at(-1)?.value ?? 0
  const latestRadioQueueSize =
    radioQueueSizePoints.at(-1)?.value ?? 0
  const radioSkipReasonItems =
    radioSkipReasons.data?.items ?? []
  const radioSkipReasonTotal = radioSkipReasonItems.reduce(
    (sum, item) => sum + item.count,
    0,
  )
  const baseOnlinePoints =
    onlinePoints.length > 0
      ? onlinePoints
      : onlineFallback
  const displayOnlinePoints = useMemo(() => {
    const source =
      onlineRangeMode === 'all'
        ? onlineFallback
        : baseOnlinePoints
    const sorted = [...source].sort((a, b) =>
      onlineSortDir === 'asc'
        ? a.ts - b.ts
        : b.ts - a.ts,
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
      <section className="admin-card admin-dashboard__hero">
        <div>
          <h2>{t('admin.dashboard.onlineHistory.title')}</h2>
          <p className="admin-card__sub">
            {t('admin.dashboard.onlineHistory.subtitle')}
          </p>
        </div>
        <div className="admin-dashboard__hero-controls">
          <AdminRangeSwitch<string>
            groupId="dash-online-range"
            value={
              onlineRangeMode === 'all' ? 'all' : String(minutes)
            }
            onChange={(v) => {
              if (v === 'all') {
                setOnlineRangeMode('all')
              } else {
                setOnlineRangeMode('range')
                setMinutes(Number(v))
              }
            }}
            options={[
              {
                value: '15',
                label: t('redesign.admin.dashboard.rangeMinutes', {
                  n: 15,
                }),
              },
              {
                value: '60',
                label: t('redesign.admin.dashboard.rangeHours', {
                  n: 1,
                }),
              },
              {
                value: '360',
                label: t('redesign.admin.dashboard.rangeHours', {
                  n: 6,
                }),
              },
              {
                value: '1440',
                label: t('redesign.admin.dashboard.rangeDay'),
              },
              {
                value: 'all',
                label: t('redesign.admin.dashboard.rangeAllTime'),
              },
            ]}
          />
          <div className="admin-dashboard__hero-toggles">
            <MotionPress
              type="button"
              variant="ghost"
              haptic="selection"
              className="admin-dashboard__hero-toggle"
              onClick={() =>
                setOnlineSortDir((v) =>
                  v === 'asc' ? 'desc' : 'asc',
                )
              }
              aria-label={
                onlineSortDir === 'asc'
                  ? t('redesign.admin.dashboard.orderOldest')
                  : t('redesign.admin.dashboard.orderNewest')
              }
            >
              {onlineSortDir === 'asc'
                ? t('redesign.admin.dashboard.orderOldest')
                : t('redesign.admin.dashboard.orderNewest')}
            </MotionPress>
            <MotionPress
              type="button"
              variant="ghost"
              haptic="selection"
              className={
                live
                  ? 'admin-dashboard__hero-toggle is-active'
                  : 'admin-dashboard__hero-toggle'
              }
              aria-pressed={live}
              onClick={() => setLive((v) => !v)}
            >
              <span
                className={
                  live
                    ? 'admin-dashboard__live-dot is-on'
                    : 'admin-dashboard__live-dot'
                }
                aria-hidden
              />
              {t('redesign.admin.dashboard.live')}
            </MotionPress>
          </div>
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
          <AdminRangeSwitch
            groupId="dash-stats-period"
            value={statsPeriod}
            onChange={setStatsPeriod}
            options={[
              {
                value: 'today',
                label: t('redesign.admin.dashboard.periodToday'),
              },
              {
                value: '7d',
                label: t('redesign.admin.dashboard.period7d'),
              },
              {
                value: '30d',
                label: t('redesign.admin.dashboard.period30d'),
              },
              {
                value: 'all',
                label: t('redesign.admin.dashboard.periodAll'),
              },
            ]}
          />
        </div>
        {stats.isLoading || !stats.data ? (
          <div className="admin-skeleton admin-skeleton--card" />
        ) : (
          <>
            <div className="admin-dashboard__metric-switch">
              <AdminRangeSwitch
                groupId="dash-stats-metric"
                value={statsMetric}
                onChange={(v) =>
                  setStatsMetric(
                    v as typeof statsMetric,
                  )
                }
                options={metricOptions}
                ariaLabel={t('admin.dashboard.stats.title')}
              />
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
                <div className="admin-range-switch adm-r-range">
                  <AdminRangeSwitch
                    groupId="dash-top-sort-by"
                    value={topSortBy}
                    onChange={setTopSortBy}
                    options={[
                      {
                        value: 'plays',
                        label: t('redesign.admin.dashboard.topByPlays'),
                      },
                      {
                        value: 'unique_listeners',
                        label: t(
                          'redesign.admin.dashboard.topByListeners',
                        ),
                      },
                    ]}
                  />
                  <MotionPress
                    type="button"
                    variant="ghost"
                    haptic="selection"
                    className="admin-range-switch__btn adm-r-range__btn"
                    onClick={() =>
                      setTopSortDir((v) =>
                        v === 'desc' ? 'asc' : 'desc',
                      )
                    }
                  >
                    {topSortDir === 'desc'
                      ? t('redesign.admin.dashboard.sortDesc')
                      : t('redesign.admin.dashboard.sortAsc')}
                  </MotionPress>
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

      <m.section
        className="kpi-grid adm-r-dash-kpi-stagger"
        variants={ADMIN_DASH_KPI_STAGGER}
        initial="hidden"
        animate="visible"
      >
        {activation.data && (
          <>
            <m.div variants={VARIANTS_FADE_UP}>
              <KpiCard
                label="Auth -> First Play (sec)"
                value={
                  activation.data.avg_auth_to_first_play_seconds
                }
              />
            </m.div>
            <m.div variants={VARIANTS_FADE_UP}>
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
            </m.div>
            <m.div variants={VARIANTS_FADE_UP}>
              <KpiCard
                label="Skip Onboarding Rate"
                value={`${Math.round(activation.data.skip_rate * 100)}%`}
                accent={
                  activation.data.skip_rate > 0.4
                    ? 'warn'
                    : 'default'
                }
              />
            </m.div>
            <m.div variants={VARIANTS_FADE_UP}>
              <KpiCard
                label="First Session Plays"
                value={
                  activation.data.first_session_plays_count
                }
              />
            </m.div>
          </>
        )}
        <m.div variants={VARIANTS_FADE_UP}>
          <KpiCard
            label={t(
              'admin.dashboard.kpi.onlineNow',
            )}
            value={data.users.online_now}
            hint={
              <>
                {t(
                  'admin.dashboard.kpi.activeAccounts',
                  {
                    count: data.users.active,
                  },
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
        </m.div>
        <m.div variants={VARIANTS_FADE_UP}>
          <KpiCard
            label={t(
              'admin.dashboard.kpi.usersTotal',
            )}
            value={data.users.total}
            hint={t(
              'admin.dashboard.kpi.newIn24h',
              {
                count: data.users.new_24h,
              },
            )}
          />
        </m.div>
        <m.div variants={VARIANTS_FADE_UP}>
          <KpiCard
            label={t('admin.dashboard.kpi.tracks')}
            value={data.tracks.total}
            hint={t(
              'admin.dashboard.kpi.newIn24h',
              {
                count: data.tracks.new_24h,
              },
            )}
          />
        </m.div>
        <m.div variants={VARIANTS_FADE_UP}>
          <KpiCard
            label={t(
              'admin.dashboard.kpi.storage',
            )}
            value={formatBytes(
              data.tracks.storage_bytes,
            )}
          />
        </m.div>
        <m.div variants={VARIANTS_FADE_UP}>
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
        </m.div>
        <m.div variants={VARIANTS_FADE_UP}>
          <KpiCard
            label={t(
              'admin.dashboard.kpi.activeJobs',
            )}
            value={data.jobs.active}
            hint={
              data.jobs.failed_1h
                ? t(
                    'admin.dashboard.kpi.failedIn1h',
                    {
                      count: data.jobs.failed_1h,
                    },
                  )
                : t(
                    'admin.dashboard.kpi.noFailures',
                  )
            }
            accent={
              data.jobs.failed_1h > 0
                ? 'warn'
                : 'default'
            }
          />
        </m.div>
        <m.div variants={VARIANTS_FADE_UP}>
          <KpiCard
            label="Radio requests / 5m"
            value={latestRadioReq.toFixed(1)}
          />
        </m.div>
        <m.div variants={VARIANTS_FADE_UP}>
          <KpiCard
            label="Radio guard hits / 5m"
            value={latestRadioGuard.toFixed(1)}
            accent={
              latestRadioGuard > 1 ? 'warn' : 'default'
            }
          />
        </m.div>
        <m.div variants={VARIANTS_FADE_UP}>
          <KpiCard
            label="Radio avg queue size"
            value={latestRadioQueueSize.toFixed(2)}
          />
        </m.div>
      </m.section>

      <section className="admin-card">
        <div className="admin-dashboard__chart-head">
          <div>
            <h2>Radio auto-skip reasons</h2>
            <p className="admin-card__sub">
              Last {radioSkipDays} {radioSkipDays === 1 ? 'day' : 'days'}
            </p>
          </div>
          <span className="admin-card__sub">
            {radioSkipReasonTotal} events
          </span>
        </div>
        {radioSkipReasons.isLoading ? (
          <div className="admin-skeleton admin-skeleton--card" />
        ) : radioSkipReasonItems.length === 0 ? (
          <div className="admin-log-empty">
            No radio auto-skip data yet
          </div>
        ) : (
          <div className="admin-dashboard__toplist-rows">
            {radioSkipReasonItems.map((item) => {
              const pct =
                radioSkipReasonTotal > 0
                  ? (item.count / radioSkipReasonTotal) * 100
                  : 0
              const reason =
                item.error_reason !== item.error_code
                  ? item.error_reason
                  : ''
              return (
                <div
                  key={`${item.error_code}:${item.error_reason}`}
                  className="admin-dashboard__toplist-row"
                >
                  <div className="admin-dashboard__toplist-title">
                    {item.error_code}
                  </div>
                  <div className="admin-dashboard__toplist-meta">
                    {item.count} events
                    {reason ? ` - ${reason}` : ''}
                  </div>
                  <div
                    aria-hidden
                    style={{
                      marginTop: 8,
                      height: 4,
                      overflow: 'hidden',
                      borderRadius: 2,
                      background: 'var(--surface-2)',
                    }}
                  >
                    <div
                      style={{
                        width: `${pct}%`,
                        height: '100%',
                        background: 'var(--text)',
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        )}
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
        <div className="admin-dashboard__chart-head">
          <div>
            <h2>Server load</h2>
            <p className="admin-card__sub">
              CPU, RAM and storage from backend host probes
            </p>
          </div>
          <span className="admin-card__sub">
            {currentResources
              ? new Date(
                  currentResources.ts * 1000,
                ).toLocaleTimeString()
              : 'waiting'}
          </span>
        </div>
      </section>
      {systemResources.isLoading || !currentResources ? (
        <div className="admin-skeleton admin-skeleton--card" />
      ) : (
        <>
          <section className="kpi-grid">
            <KpiCard
              label="CPU"
              value={formatPercent(currentResources.cpu_pct)}
              hint={
                currentResources.load_avg.one !== null
                  ? `load avg ${currentResources.load_avg.one.toFixed(2)}`
                  : 'load avg n/a'
              }
              accent={resourceAccent(
                currentResources.cpu_pct,
              )}
            />
            <KpiCard
              label="RAM"
              value={formatPercent(
                currentResources.memory.used_pct,
              )}
              hint={
                currentResources.memory.used_bytes !== null &&
                currentResources.memory.total_bytes !== null
                  ? `${formatBytes(
                      currentResources.memory.used_bytes,
                    )} / ${formatBytes(
                      currentResources.memory.total_bytes,
                    )}`
                  : 'memory n/a'
              }
              accent={resourceAccent(
                currentResources.memory.used_pct,
              )}
            />
            <KpiCard
              label="Storage"
              value={formatPercent(
                currentResources.storage.used_pct,
              )}
              hint={
                currentResources.storage.used_bytes !== null &&
                currentResources.storage.total_bytes !== null
                  ? `${formatBytes(
                      currentResources.storage.used_bytes,
                    )} / ${formatBytes(
                      currentResources.storage.total_bytes,
                    )}`
                  : currentResources.storage.path
              }
              accent={resourceAccent(
                currentResources.storage.used_pct,
              )}
            />
          </section>
          <section className="kpi-grid kpi-grid--charts">
            <article className="admin-card">
              <h2>CPU history</h2>
              <LineChart
                data={cpuPoints}
                height={180}
                ariaLabel="CPU history"
              />
            </article>
            <article className="admin-card">
              <h2>RAM history</h2>
              <LineChart
                data={memoryPoints}
                height={180}
                ariaLabel="RAM history"
              />
            </article>
            <article className="admin-card">
              <h2>Storage history</h2>
              <LineChart
                data={storagePoints}
                height={180}
                ariaLabel="Storage history"
              />
            </article>
          </section>
        </>
      )}
      <details className="admin-dashboard__collapse">
        <summary className="admin-dashboard__collapse-summary">
          <span className="admin-dashboard__collapse-title">
            {t(
              'admin.dashboard.outbound.title',
              'Outbound network',
            )}
          </span>
          <span
            className="admin-dashboard__collapse-chev"
            aria-hidden
          >
            ▾
          </span>
        </summary>
        <OutboundStatusPanel />
      </details>

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
