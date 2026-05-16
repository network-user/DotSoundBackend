import {
  useEffect,
  useId,
  useMemo,
  useState,
} from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

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

const CHART_WIDTH = 640
const CHART_HEIGHT = 220
const CHART_PAD_LEFT = 48
const CHART_PAD_RIGHT = 18
const CHART_PAD_TOP = 12
const CHART_PAD_BOTTOM = 30

function formatChartValue(value: number): string {
  return fmtCount(value)
}

function StatsMetricChart({
  data,
  metric,
  metricLabel,
  area = false,
  ariaLabel,
}: {
  data: ChartRow[]
  metric: MetricKey
  metricLabel: string
  area?: boolean
  ariaLabel: string
}) {
  const gradientId = useId().replace(/:/g, '')
  const clean = data.filter((row) =>
    Number.isFinite(row[metric]),
  )
  if (clean.length === 0) {
    return <div className="empty-state" />
  }

  const plotWidth =
    CHART_WIDTH - CHART_PAD_LEFT - CHART_PAD_RIGHT
  const plotHeight =
    CHART_HEIGHT - CHART_PAD_TOP - CHART_PAD_BOTTOM
  const maxValue = Math.max(1, ...clean.map((row) => row[metric]))
  const yMax = maxValue * 1.08
  const xRange = Math.max(1, clean.length - 1)
  const points = clean.map((row, index) => {
    const x =
      CHART_PAD_LEFT + (index / xRange) * plotWidth
    const y =
      CHART_PAD_TOP +
      plotHeight -
      (row[metric] / yMax) * plotHeight
    return { row, x, y }
  })
  const linePath = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`)
    .join(' ')
  const bottom = CHART_PAD_TOP + plotHeight
  const areaPath =
    points.length > 0
      ? `${linePath} L${points[points.length - 1].x},${bottom} L${
          points[0].x
        },${bottom} Z`
      : ''
  const yTicks = [0, yMax / 3, (yMax * 2) / 3, yMax]
    .map((value) => ({
      value,
      y:
        CHART_PAD_TOP +
        plotHeight -
        (value / yMax) * plotHeight,
    }))
    .reverse()
  const xLabels =
    clean.length <= 2
      ? clean
      : [
          clean[0],
          clean[Math.floor((clean.length - 1) / 2)],
          clean[clean.length - 1],
        ]

  return (
    <svg
      className="stats-chart-svg"
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      role="img"
      aria-label={ariaLabel}
    >
      <defs>
        <linearGradient
          id={gradientId}
          x1="0"
          y1="0"
          x2="0"
          y2="1"
        >
          <stop
            offset="0%"
            stopColor="currentColor"
            stopOpacity={0.32}
          />
          <stop
            offset="100%"
            stopColor="currentColor"
            stopOpacity={0}
          />
        </linearGradient>
      </defs>
      <g className="stats-chart-grid" aria-hidden>
        {yTicks.map((tick) => (
          <g key={tick.value}>
            <line
              x1={CHART_PAD_LEFT}
              x2={CHART_WIDTH - CHART_PAD_RIGHT}
              y1={tick.y}
              y2={tick.y}
            />
            <text
              x={CHART_PAD_LEFT - 8}
              y={tick.y + 4}
              textAnchor="end"
            >
              {formatChartValue(tick.value)}
            </text>
          </g>
        ))}
      </g>
      {area && (
        <path
          d={areaPath}
          fill={`url(#${gradientId})`}
        />
      )}
      <path
        d={linePath}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        vectorEffect="non-scaling-stroke"
      />
      {points.map((point) => (
        <circle
          key={point.row.fullName}
          cx={point.x}
          cy={point.y}
          r={3}
          fill="currentColor"
        >
          <title>
            {point.row.fullName}: {formatChartValue(point.row[metric])}{' '}
            {metricLabel}
          </title>
        </circle>
      ))}
      <g className="stats-chart-axis" aria-hidden>
        {xLabels.map((row) => {
          const index = clean.indexOf(row)
          const x =
            CHART_PAD_LEFT + (index / xRange) * plotWidth
          return (
            <text
              key={row.fullName}
              x={x}
              y={CHART_HEIGHT - 8}
              textAnchor={
                index === 0
                  ? 'start'
                  : index === clean.length - 1
                    ? 'end'
                    : 'middle'
              }
            >
              {row.name}
            </text>
          )
        })}
      </g>
    </svg>
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
                  <StatsMetricChart
                    data={chartData}
                    metric="listeners"
                    metricLabel={t('artistStats.listeners')}
                    area
                    ariaLabel={t('artistStats.aria.chartListeners')}
                  />
                </div>
              </section>

              <ChartLineCard
                titleKey="artistStats.totalPlays"
                ariaKey="artistStats.aria.chartPlays"
                metric="plays"
                metricLabelKey="artistStats.plays"
                data={chartData}
                t={t}
                accentClass="stats-chart-card--accent"
              />

              <ChartLineCard
                titleKey="artistStats.totalLikes"
                ariaKey="artistStats.aria.chartLikes"
                metric="likes"
                metricLabelKey="artistStats.likes"
                data={chartData}
                t={t}
                accentClass="stats-chart-card--muted"
              />

              <ChartLineCard
                titleKey="artistStats.totalFollowers"
                ariaKey="artistStats.aria.chartFollowers"
                metric="followers"
                metricLabelKey="artistStats.followers"
                data={chartData}
                t={t}
                accentClass="stats-chart-card--muted"
              />

              <section
                className="stats-history-table-section"
                aria-label={t('artistStats.historyTable')}
              >
                <h3 className="stats-history-table-title">
                  {t('artistStats.historyTable')}
                </h3>
                <div className="stats-history-table-wrap">
                  <table className="stats-history-table">
                    <thead>
                      <tr>
                        <th>{t('artistStats.col.month')}</th>
                        <th>{t('artistStats.col.listeners')}</th>
                        <th>{t('artistStats.col.plays')}</th>
                        <th>{t('artistStats.col.likes')}</th>
                        <th>{t('artistStats.col.followers')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...sortedHistory]
                        .reverse()
                        .map((r) => (
                          <tr
                            key={`${r.year}-${r.month}`}
                          >
                            <td>
                              {monthFmt.long(
                                r.year,
                                r.month,
                              )}
                            </td>
                            <td>
                              {fmtCount(r.unique_listeners)}
                            </td>
                            <td>
                              {fmtCount(r.total_plays)}
                            </td>
                            <td>
                              {fmtCount(r.total_likes)}
                            </td>
                            <td>
                              {fmtCount(r.total_followers)}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </section>
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
  t: (key: string, opts?: Record<string, unknown>) => string
  accentClass: string
}

function ChartLineCard({
  titleKey,
  ariaKey,
  metric,
  metricLabelKey,
  data,
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
        <StatsMetricChart
          data={data}
          metric={metric}
          metricLabel={t(metricLabelKey)}
          ariaLabel={t(ariaKey)}
        />
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
        box-shadow:
          0 10px 22px rgba(0, 0, 0, 0.16),
          inset 0 1px 0 rgba(255, 255, 255, 0.06);
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
        box-shadow:
          0 10px 22px rgba(0, 0, 0, 0.16),
          inset 0 1px 0 rgba(255, 255, 255, 0.06);
        transition:
          transform 150ms ease,
          border-color 150ms ease,
          box-shadow 150ms ease;
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
        box-shadow:
          0 12px 24px rgba(0, 0, 0, 0.17),
          inset 0 1px 0 rgba(255, 255, 255, 0.06);
        transition:
          transform 150ms ease,
          border-color 150ms ease,
          box-shadow 150ms ease;
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
      .stats-chart-svg {
        display: block;
        width: 100%;
        height: 100%;
        overflow: visible;
      }
      .stats-chart-grid line {
        stroke: var(--border);
        stroke-width: 1;
        vector-effect: non-scaling-stroke;
      }
      .stats-chart-grid text,
      .stats-chart-axis text {
        fill: var(--text-secondary);
        font-size: 11px;
      }
      .artist-stats-view .back-btn:focus-visible,
      .stats-kpi-card:focus-within,
      .stats-chart-card:focus-within {
        outline: 2px solid var(--accent);
        outline-offset: 2px;
      }
      @media (hover: hover) and (pointer: fine) {
        .stats-kpi-card:hover {
          transform: translateY(-1px);
          border-color: color-mix(in srgb, var(--accent) 22%, var(--border));
          box-shadow:
            0 14px 28px rgba(0, 0, 0, 0.2),
            inset 0 1px 0 rgba(255, 255, 255, 0.08);
        }
        .stats-chart-card:hover {
          transform: translateY(-1px);
          border-color: color-mix(in srgb, var(--accent) 18%, var(--border));
          box-shadow:
            0 16px 30px rgba(0, 0, 0, 0.22),
            inset 0 1px 0 rgba(255, 255, 255, 0.08);
        }
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
      .stats-history-table-section {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius-lg);
        padding: 14px;
        box-shadow:
          0 10px 22px rgba(0, 0, 0, 0.16),
          inset 0 1px 0 rgba(255, 255, 255, 0.06);
      }
      .stats-history-table-title {
        margin: 0 0 12px 0;
        font-size: 0.95rem;
        color: var(--text);
        font-weight: 600;
      }
      .stats-history-table-wrap {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
      }
      .stats-history-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
        font-variant-numeric: tabular-nums;
      }
      .stats-history-table th {
        text-align: right;
        padding: 6px 10px;
        color: var(--text-secondary);
        font-weight: 500;
        font-size: 0.78rem;
        border-bottom: 1px solid var(--border);
        white-space: nowrap;
      }
      .stats-history-table th:first-child {
        text-align: left;
      }
      .stats-history-table td {
        text-align: right;
        padding: 7px 10px;
        color: var(--text);
        border-bottom: 1px solid
          color-mix(in srgb, var(--border) 50%, transparent);
      }
      .stats-history-table td:first-child {
        text-align: left;
        color: var(--text-secondary);
        white-space: nowrap;
      }
      .stats-history-table tr:last-child td {
        border-bottom: none;
      }
    `}</style>
  )
}
