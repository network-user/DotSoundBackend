import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'

interface ListenerStats {
  period_days: number
  minutes_listened: number
  tracks_listened: number
  top_artists: { name: string; minutes: number; plays: number }[]
  top_genres: { name: string; minutes: number; plays: number }[]
}

const PERIODS: { id: 7 | 30 | 365; key: string; defaultLabel: string }[] = [
  { id: 7, key: 'profile.listenStats.period_7', defaultLabel: '7 дней' },
  { id: 30, key: 'profile.listenStats.period_30', defaultLabel: '30 дней' },
  { id: 365, key: 'profile.listenStats.period_365', defaultLabel: 'Год' },
]

function formatMinutes(min: number): string {
  if (min < 60) return `${min} мин`
  const h = Math.floor(min / 60)
  const m = min - h * 60
  return m > 0 ? `${h} ч ${m} мин` : `${h} ч`
}

export function ListenerStats() {
  const { t } = useTranslation()
  const [period, setPeriod] = useState<7 | 30 | 365>(30)
  const [data, setData] = useState<ListenerStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .getMyListeningStats(period)
      .then((res) => {
        if (!cancelled) {
          setData(res as ListenerStats)
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setData(null)
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [period])

  const minutes = data?.minutes_listened ?? 0
  const tracks = data?.tracks_listened ?? 0
  const topArtist = data?.top_artists?.[0]
  const topGenre = data?.top_genres?.[0]

  return (
    <div className="listener-stats" style={{ marginTop: 12 }}>
      <div
        className="listener-stats__header"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 8,
        }}
      >
        <div style={{ fontWeight: 600, fontSize: 14 }}>
          {t('profile.listenStats.title', 'Ваше прослушивание')}
        </div>
        <div
          role="tablist"
          style={{ display: 'flex', gap: 4 }}
          aria-label={t(
            'profile.listenStats.periodAria',
            'Период статистики',
          )}
        >
          {PERIODS.map((p) => (
            <button
              key={p.id}
              type="button"
              role="tab"
              aria-selected={period === p.id}
              className={`pb-extras-btn${
                period === p.id ? ' active' : ''
              }`}
              onClick={() => setPeriod(p.id)}
            >
              {t(p.key, p.defaultLabel)}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="profile-stats">
          <div className="stat-item">
            <div className="stat-value">…</div>
            <div className="stat-label">
              {t(
                'profile.listenStats.minutes',
                'Минуты',
              )}
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-value">…</div>
            <div className="stat-label">
              {t(
                'profile.listenStats.tracks',
                'Уник. треков',
              )}
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-value">…</div>
            <div className="stat-label">
              {t(
                'profile.listenStats.topArtist',
                'Топ-артист',
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="profile-stats">
          <div className="stat-item">
            <div className="stat-value">
              {minutes > 0 ? formatMinutes(minutes) : '—'}
            </div>
            <div className="stat-label">
              {t(
                'profile.listenStats.minutes',
                'Минуты',
              )}
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{tracks || '—'}</div>
            <div className="stat-label">
              {t(
                'profile.listenStats.tracks',
                'Уник. треков',
              )}
            </div>
          </div>
          <div className="stat-item">
            <div
              className="stat-value"
              style={{
                fontSize: 16,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
              title={topArtist?.name}
            >
              {topArtist?.name || '—'}
            </div>
            <div className="stat-label">
              {t(
                'profile.listenStats.topArtist',
                'Топ-артист',
              )}
            </div>
          </div>
          {topGenre && (
            <div className="stat-item">
              <div
                className="stat-value"
                style={{ fontSize: 16 }}
                title={topGenre.name}
              >
                {topGenre.name}
              </div>
              <div className="stat-label">
                {t(
                  'profile.listenStats.topGenre',
                  'Топ-жанр',
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
