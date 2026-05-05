import { useEffect, useState } from 'react'
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
import type { ArtistListenersResponse, ArtistDetail } from '@/types/api'

const MONTH_LABELS = [
  'Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
  'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек',
]

function fmtCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export function ArtistStatsView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const artistId = Number(id)

  const [artist, setArtist] = useState<ArtistDetail | null>(null)
  const [stats, setStats] = useState<ArtistListenersResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (isNaN(artistId)) return

    setLoading(true)
    Promise.all([
      api.getArtist(artistId),
      api.getArtistListeners(artistId),
    ])
      .then(([a, s]) => {
        setArtist(a)
        setStats(s)
      })
      .catch((err) => {
        console.error('[ArtistStatsView] load failed', err)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [artistId])

  if (loading) {
    return <div className="loader" />
  }

  if (!artist || !stats) {
    return (
      <div className="view-container">
        <div className="view-header">
          <button className="back-btn" onClick={() => navigate(-1)}>
            <Icon name="chevron-left" />
          </button>
        </div>
        <div className="empty-state">
          <Icon name="alert-circle" size={48} />
          <p>{t('common.unknownError')}</p>
        </div>
      </div>
    )
  }

  const chartData = [...stats.history]
    .sort((a, b) => (a.year !== b.year ? a.year - b.year : a.month - b.month))
    .map((r) => ({
      name: `${MONTH_LABELS[r.month - 1]} ${r.year}`,
      listeners: r.unique_listeners,
      plays: r.total_plays,
      likes: r.total_likes,
      followers: r.total_followers,
    }))

  const hasHistory = chartData.length > 0

  return (
    <div className="view-container artist-stats-view">
      <div className="view-header sticky">
        <button className="back-btn" onClick={() => navigate(-1)}>
          <Icon name="chevron-left" />
          <span>{t('artistStats.back')}</span>
        </button>
        <h1 className="view-title">
          {t('artistStats.title', { name: artist.name })}
        </h1>
      </div>

      <div className="view-content">
        {!hasHistory ? (
          <div className="empty-state">
            <Icon name="bar-chart" size={48} />
            <p>{t('artistStats.noData')}</p>
          </div>
        ) : (
          <div className="stats-charts-grid">
            {/* Unique Listeners */}
            <section className="stats-chart-card">
              <h3>{t('artistStats.monthlyListeners')}</h3>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="colorListeners" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                    <XAxis
                      dataKey="name"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                      tickFormatter={fmtCount}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--bg-card)',
                        borderColor: 'var(--border)',
                        color: 'var(--text-primary)',
                      }}
                      formatter={(val: number) => [fmtCount(val), t('artistStats.listeners')]}
                    />
                    <Area
                      type="monotone"
                      dataKey="listeners"
                      stroke="var(--accent)"
                      fillOpacity={1}
                      fill="url(#colorListeners)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </section>

            {/* Total Plays */}
            <section className="stats-chart-card">
              <h3>{t('artistStats.totalPlays')}</h3>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                    <XAxis
                      dataKey="name"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                      tickFormatter={fmtCount}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--bg-card)',
                        borderColor: 'var(--border)',
                        color: 'var(--text-primary)',
                      }}
                      formatter={(val: number) => [fmtCount(val), t('artistStats.plays')]}
                    />
                    <Line
                      type="monotone"
                      dataKey="plays"
                      stroke="#4ade80"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>

            {/* Total Likes */}
            <section className="stats-chart-card">
              <h3>{t('artistStats.totalLikes')}</h3>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                    <XAxis
                      dataKey="name"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                      tickFormatter={fmtCount}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--bg-card)',
                        borderColor: 'var(--border)',
                        color: 'var(--text-primary)',
                      }}
                      formatter={(val: number) => [fmtCount(val), t('artistStats.likes')]}
                    />
                    <Line
                      type="monotone"
                      dataKey="likes"
                      stroke="#f43f5e"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>

            {/* Total Followers */}
            <section className="stats-chart-card">
              <h3>{t('artistStats.totalFollowers')}</h3>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                    <XAxis
                      dataKey="name"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                      tickFormatter={fmtCount}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--bg-card)',
                        borderColor: 'var(--border)',
                        color: 'var(--text-primary)',
                      }}
                      formatter={(val: number) => [fmtCount(val), t('artistStats.followers')]}
                    />
                    <Line
                      type="monotone"
                      dataKey="followers"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          </div>
        )}
      </div>

      <style>{`
        .artist-stats-view .view-header {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 12px 16px;
          background: var(--bg-main);
          z-index: 10;
        }
        .artist-stats-view .view-title {
          font-size: 1.2rem;
          margin: 0;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .artist-stats-view .back-btn {
          display: flex;
          align-items: center;
          gap: 4px;
          background: none;
          border: none;
          color: var(--text-primary);
          font-size: 0.9rem;
          padding: 4px 8px 4px 4px;
          border-radius: 8px;
          transition: background 0.2s;
        }
        .artist-stats-view .back-btn:active {
          background: var(--bg-highlight);
        }
        .stats-charts-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 24px;
          padding: 16px;
          padding-bottom: 120px;
        }
        .stats-chart-card {
          background: var(--bg-card);
          border-radius: 16px;
          padding: 16px;
          border: 1px solid var(--border);
        }
        .stats-chart-card h3 {
          margin: 0 0 16px 0;
          font-size: 1rem;
          color: var(--text-primary);
          font-weight: 600;
        }
        .chart-container {
          height: 240px;
          width: 100%;
        }
      `}</style>
    </div>
  )
}
