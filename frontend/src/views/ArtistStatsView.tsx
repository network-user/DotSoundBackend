import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts'

import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import type {
  ArtistListenersResponse,
  ArtistDetail,
  MonthlyListenersEntry,
} from '@/types/api'

type MetricKey = 'listeners' | 'plays' | 'likes' | 'followers'

interface ChartRow {
  name: string
  fullName: string
  listeners: number
  plays: number
  likes: number
  followers: number
}

interface KpiCardData {
  key: MetricKey
  labelKey: string
  ariaKey: string
  value: number
  trend: number | null
}

function fmtCount(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(Math.round(n))
}

function buildMonthFormatters(lang: string) {
  const safeLang = lang || 'en'
  let shortFmt: Intl.DateTimeFormat
  let longFmt: Intl.DateTimeFormat
  try {
    shortFmt = new Intl.DateTimeFormat(safeLang, {
      month: 'short',
    })
    longFmt = new Intl.DateTimeFormat(safeLang, {
      month: 'long',
      year: 'numeric',
    })
  } catch {
    shortFmt = new Intl.DateTimeFormat('en', { month: 'short' })
    longFmt = new Intl.DateTimeFormat('en', {
      month: 'long',
      year: 'numeric',
    })
  }
  return {
    short: (year: number, month: number) => {
      const d = new Date(Date.UTC(year, month - 1, 1))
      return shortFmt.format(d)
    },
    long: (year: number, month: number) => {
      const d = new Date(Date.UTC(year, month - 1, 1))
      return longFmt.format(d)
    },
  }
}

function sortHistory(
  history: MonthlyListenersEntry[],
): MonthlyListenersEntry[] {
  return [...history].sort((a, b) =>
    a.year !== b.year ? a.year - b.year : a.month - b.month,
  )
}

function computeTrend(
  current: number,
  previous: number,
): number | null {
  if (!Number.isFinite(previous) || previous <= 0) {
    return current > 0 ? 100 : null
  }
  return ((current - previous) / previous) * 100
}

function KpiCard({
  card,
  loading,
  t,
}: {
  card: KpiCardData
  loading: boolean
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  const trend = card.trend
  const hasTrend = trend !== null && Number.isFinite(trend)
  const direction =
    !hasTrend
      ? 'flat'
      : trend! > 0.5
        ? 'up'
        : trend! < -0.5
          ? 'down'
          : 'flat'
  const trendLabel = hasTrend
    ? `${trend! > 0 ? '+' : ''}${trend!.toFixed(1)}%`
    : t('artistStats.kpi.noPrev')

  return (
    <div
      className="stats-kpi-card"
      role="group"
      aria-label={t(card.ariaKey)}
    >
      <span className="stats-kpi-label">
        {t(card.labelKey)}
      </span>
      <span
        className="stats-kpi-value"
        aria-live="polite"
      >
        {loading ? '—' : fmtCount(card.value)}
      </span>
      <span
        className={`stats-kpi-trend stats-kpi-trend--${direction}`}
      >
        {direction === 'up' && (
          <Icon name="chevron" size={12} />
        )}
        {direction === 'down' && (
          <Icon name="chevron" size={12} />
        )}
        {trendLabel}
      </span>
    </div>
  )
}

function ChartSkeleton() {
  return (
    <div className="stats-charts-grid" aria-busy="true">
      <div className="stats-kpi-row">
        <div className="stats-kpi-card stats-kpi-card--skeleton" />
        <div className="stats-kpi-card stats-kpi-card--skeleton" />
        <div className="stats-kpi-card stats-kpi-card--skeleton" />
        <div className="stats-kpi-card stats-kpi-card--skeleton" />
      </div>
      <div className="stats-chart-card stats-chart-card--skeleton" />
      <div className="stats-chart-card stats-chart-card--skeleton" />
      <div className="stats-chart-card stats-chart-card--skeleton" />
    </div>
  )
}

export function ArtistStatsView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t, i18n } = useTranslation()
  const artistId = Number(id)

  const [artist, setArtist] = useState<ArtistDetail | null>(null)
  const [stats, setStats] =
    useState<ArtistListenersResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (Number.isNaN(artistId)) {
      setLoading(false)
      setFailed(true)
      return
    }

    let cancelled = false
    setLoading(true)
    setFailed(false)

    Promise.all([
      api.getArtist(artistId),
      api.getArtistListeners(artistId),
    ])
      .then(([a, s]) => {
        if (cancelled) return
        setArtist(a)
        setStats(s)
      })
      .catch((err) => {
        if (cancelled) return
        console.error('[ArtistStatsView] load failed', err)
        setFailed(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [artistId])

  const monthFmt = useMemo(
    () => buildMonthFormatters(i18n.language),
    [i18n.language],
  )

  const sortedHistory = useMemo(
    () => (stats ? sortHistory(stats.history) : []),
    [stats],
  )

  const chartData = useMemo<ChartRow[]>(
    () =>
      sortedHistory.map((r) => ({
        name: monthFmt.short(r.year, r.month),
        fullName: monthFmt.long(r.year, r.month),
        listeners: r.unique_listeners,
        plays: r.total_plays,
        likes: r.total_likes,
        followers: r.total_followers,
      })),
    [sortedHistory, monthFmt],
  )

  const kpis = useMemo<KpiCardData[]>(() => {
    const last = sortedHistory[sortedHistory.length - 1]
    const prev = sortedHistory[sortedHistory.length - 2]
    const fallbackListeners =
      stats?.current_month_listeners ?? 0

    const buildKpi = (
      key: MetricKey,
      labelKey: string,
      ariaKey: string,
      currentValue: number,
      prevValue: number | null,
    ): KpiCardData => ({
      key,
      labelKey,
      ariaKey,
      value: currentValue,
      trend:
        prevValue !== null
          ? computeTrend(currentValue, prevValue)
          : null,
    })

    return [
      buildKpi(
        'listeners',
        'artistStats.kpi.listenersThisMonth',
        'artistStats.aria.listenersCard',
        last?.unique_listeners ?? fallbackListeners,
        prev?.unique_listeners ?? null,
      ),
      buildKpi(
        'plays',
        'artistStats.kpi.playsThisMonth',
        'artistStats.aria.playsCard',
        last?.total_plays ?? 0,
        prev?.total_plays ?? null,
      ),
      buildKpi(
        'likes',
        'artistStats.kpi.likesThisMonth',
        'artistStats.aria.likesCard',
        last?.total_likes ?? 0,
        prev?.total_likes ?? null,
      ),
      buildKpi(
        'followers',
        'artistStats.kpi.followersThisMonth',
        'artistStats.aria.followersCard',
        last?.total_followers ?? 0,
        prev?.total_followers ?? null,
      ),
    ]
  }, [sortedHistory, stats])

  if (loading) {
    return (
      <div className="view-container artist-stats-view">
        <div className="view-header sticky">
          <button
            className="back-btn"
            onClick={() => navigate(-1)}
            aria-label={t('artistStats.back')}
          >
            <Icon name="chevron-left" />
            <span>{t('artistStats.back')}</span>
          </button>
        </div>
        <div className="view-content">
          <ChartSkeleton />
        </div>
        <ArtistStatsStyles />
      </div>
    )
  }

  if (failed || !artist || !stats) {
    return (
      <div className="view-container artist-stats-view">
        <div className="view-header sticky">
          <button
            className="back-btn"
            onClick={() => navigate(-1)}
            aria-label={t('artistStats.back')}
          >
            <Icon name="chevron-left" />
            <span>{t('artistStats.back')}</span>
          </button>
        </div>
        <div className="empty-state">
          <Icon name="alert-circle" size={48} />
          <p>{t('common.unknownError')}</p>
        </div>
        <ArtistStatsStyles />
      </div>
    )
  }

  const hasHistory = chartData.length > 0
  const tooltipContentStyle = {
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    color: 'var(--text)',
    fontSize: '0.85rem',
    padding: '8px 12px',
  }

  return (
    <div className="view-container artist-stats-view">
      <div className="view-header sticky">
        <button
          className="back-btn"
          onClick={() => navigate(-1)}
          aria-label={t('artistStats.back')}
        >
          <Icon name="chevron-left" />
          <span>{t('artistStats.back')}</span>
        </button>
        <h1 className="view-title">
          {t('artistStats.title', { name: artist.name })}
        </h1>
      </div>

      <div className="view-content">
        <div className="stats-charts-grid">
          <div
            className="stats-kpi-row"
            role="region"
            aria-label={t('artistStats.aria.kpiRegion')}
          >
            {kpis.map((card) => (
              <KpiCard
                key={card.key}
                card={card}
                loading={false}
                t={t}
              />
            ))}
          </div>

          {!hasHistory ? (
            <div className="empty-state">
              <Icon name="bar-chart" size={48} />
              <p>{t('artistStats.noData')}</p>
            </div>
          ) : (
            <>
              <section
                className="stats-chart-card stats-chart-card--accent"
                role="region"
                aria-label={t('artistStats.aria.chartListeners')}
              >
                <h3>{t('artistStats.monthlyListeners')}</h3>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                      <defs>
                        <linearGradient
                          id="colorListeners"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="currentColor"
                            stopOpacity={0.35}
                          />
                          <stop
                            offset="100%"
                            stopColor="currentColor"
                            stopOpacity={0}
                          />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke="var(--border)"
                      />
                      <XAxis
                        dataKey="name"
                        axisLine={false}
                        tickLine={false}
                        tick={{
                          fill: 'var(--text-secondary)',
                          fontSize: 12,
                        }}
                      />
                      <YAxis
                        axisLine={false}
                        tickLine={false}
                        tick={{
                          fill: 'var(--text-secondary)',
                          fontSize: 12,
                        }}
                        tickFormatter={fmtCount}
                        width={48}
                      />
                      <Tooltip
                        contentStyle={tooltipContentStyle}
                        labelFormatter={(label) => {
                          const row = chartData.find(
                            (r) => r.name === label,
                          )
                          return row?.fullName ?? String(label)
                        }}
                        formatter={(val: number) => [
                          fmtCount(val),
                          t('artistStats.listeners'),
                        ]}
                      />
                      <Area
                        type="monotone"
                        dataKey="listeners"
                        stroke="currentColor"
                        strokeWidth={2}
                        fill="url(#colorListeners)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </section>

              <ChartLineCard
                titleKey="artistStats.totalPlays"
                ariaKey="artistStats.aria.chartPlays"
                metric="plays"
                metricLabelKey="artistStats.plays"
                data={chartData}
                tooltipContentStyle={tooltipContentStyle}
                t={t}
                accentClass="stats-chart-card--accent"
              />

              <ChartLineCard
                titleKey="artistStats.totalLikes"
                ariaKey="artistStats.aria.chartLikes"
                metric="likes"
                metricLabelKey="artistStats.likes"
                data={chartData}
                tooltipContentStyle={tooltipContentStyle}
                t={t}
                accentClass="stats-chart-card--muted"
              />

              <ChartLineCard
                titleKey="artistStats.totalFollowers"
                ariaKey="artistStats.aria.chartFollowers"
                metric="followers"
                metricLabelKey="artistStats.followers"
                data={chartData}
                tooltipContentStyle={tooltipContentStyle}
                t={t}
                accentClass="stats-chart-card--muted"
              />
            </>
          )}
        </div>
      </div>

      <ArtistStatsStyles />
    </div>
  )
}

interface ChartLineCardProps {
  titleKey: string
  ariaKey: string
  metric: 'plays' | 'likes' | 'followers'
  metricLabelKey: string
  data: ChartRow[]
  tooltipContentStyle: Record<string, string>
  t: (key: string, opts?: Record<string, unknown>) => string
  accentClass: string
}

function ChartLineCard({
  titleKey,
  ariaKey,
  metric,
  metricLabelKey,
  data,
  tooltipContentStyle,
  t,
  accentClass,
}: ChartLineCardProps) {
  return (
    <section
      className={`stats-chart-card ${accentClass}`}
      role="region"
      aria-label={t(ariaKey)}
    >
      <h3>{t(titleKey)}</h3>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="var(--border)"
            />
            <XAxis
              dataKey="name"
              axisLine={false}
              tickLine={false}
              tick={{
                fill: 'var(--text-secondary)',
                fontSize: 12,
              }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{
                fill: 'var(--text-secondary)',
                fontSize: 12,
              }}
              tickFormatter={fmtCount}
              width={48}
            />
            <Tooltip
              contentStyle={tooltipContentStyle}
              labelFormatter={(label) => {
                const row = data.find(
                  (r) => r.name === label,
                )
                return row?.fullName ?? String(label)
              }}
              formatter={(val: number) => [
                fmtCount(val),
                t(metricLabelKey),
              ]}
            />
            <Line
              type="monotone"
              dataKey={metric}
              stroke="currentColor"
              strokeWidth={2}
              dot={{
                r: 3,
                fill: 'currentColor',
                stroke: 'currentColor',
              }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

function ArtistStatsStyles() {
  return (
    <style>{`
      .artist-stats-view {
        color: var(--text);
      }
      .artist-stats-view .view-header.sticky {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: calc(env(safe-area-inset-top) + 12px) 16px 12px;
        background: var(--bg);
        position: sticky;
        top: 0;
        z-index: 10;
        border-bottom: 1px solid var(--border);
      }
      .artist-stats-view .view-title {
        font-size: 1.05rem;
        margin: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        color: var(--text);
        font-weight: 600;
      }
      .artist-stats-view .back-btn {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: none;
        border: none;
        color: var(--text);
        font-size: 0.9rem;
        padding: 6px 8px 6px 4px;
        border-radius: 8px;
        transition: background 0.18s ease;
        cursor: pointer;
      }
      .artist-stats-view .back-btn:hover,
      .artist-stats-view .back-btn:active {
        background: var(--bg-card-hover);
      }
      .stats-charts-grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 16px;
        padding: 16px;
        padding-bottom: calc(
          var(--player-h) + env(safe-area-inset-bottom) + var(--nav-h) + 16px
        );
      }
      .stats-kpi-row {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }
      @media (min-width: 720px) {
        .stats-kpi-row {
          grid-template-columns: repeat(4, minmax(0, 1fr));
        }
      }
      .stats-kpi-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius-lg);
        padding: 14px 14px 12px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        min-height: 92px;
      }
      .stats-kpi-card--skeleton {
        min-height: 92px;
        background: linear-gradient(
          90deg,
          var(--bg-card) 0%,
          var(--bg-card-hover) 50%,
          var(--bg-card) 100%
        );
        background-size: 200% 100%;
        animation: stats-skeleton-shimmer 1.6s ease-in-out infinite;
      }
      .stats-kpi-label {
        font-size: 0.78rem;
        color: var(--text-secondary);
        font-weight: 500;
        letter-spacing: 0.01em;
      }
      .stats-kpi-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--text);
        line-height: 1.1;
        font-variant-numeric: tabular-nums;
      }
      .stats-kpi-trend {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        font-size: 0.78rem;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
      }
      .stats-kpi-trend--up {
        color: var(--state-ok);
      }
      .stats-kpi-trend--up :global(svg),
      .stats-kpi-trend--up svg {
        transform: rotate(180deg);
      }
      .stats-kpi-trend--down {
        color: var(--state-error);
      }
      .stats-kpi-trend--flat {
        color: var(--text-muted);
      }
      .stats-chart-card {
        background: var(--bg-card);
        border-radius: var(--radius-lg);
        padding: 14px;
        border: 1px solid var(--border);
        color: var(--accent);
      }
      .stats-chart-card--muted {
        color: var(--text-secondary);
      }
      .stats-chart-card--skeleton {
        height: 240px;
        background: linear-gradient(
          90deg,
          var(--bg-card) 0%,
          var(--bg-card-hover) 50%,
          var(--bg-card) 100%
        );
        background-size: 200% 100%;
        animation: stats-skeleton-shimmer 1.6s ease-in-out infinite;
      }
      .stats-chart-card h3 {
        margin: 0 0 12px 0;
        font-size: 0.95rem;
        color: var(--text);
        font-weight: 600;
      }
      .chart-container {
        position: relative;
        width: 100%;
        aspect-ratio: 16 / 7;
        min-height: 200px;
      }
      @media (prefers-reduced-motion: reduce) {
        .stats-kpi-card--skeleton,
        .stats-chart-card--skeleton {
          animation: none;
        }
      }
      @keyframes stats-skeleton-shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
      }
    `}</style>
  )
}
