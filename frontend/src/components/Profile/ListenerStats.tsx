import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'
import {
  Sparkline,
  type SparklinePoint,
} from '@/components/Profile/Sparkline'
import { StatsRowSkeleton } from '@/components/Profile/Skeleton'

interface ListenerStats {
  period_days: number
  minutes_listened: number
  tracks_listened: number
  top_artists: { name: string; minutes: number; plays: number }[]
  top_genres: { name: string; minutes: number; plays: number }[]
}

const PROFILE_TODAY_PERIOD_DAYS = 1

function formatMinutes(min: number): string {
  if (min < 60) return `${min} мин`
  const h = Math.floor(min / 60)
  const m = min - h * 60
  return m > 0 ? `${h} ч ${m} мин` : `${h} ч`
}

export function ListenerStats() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [data, setData] = useState<ListenerStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [trend, setTrend] = useState<SparklinePoint[]>([])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .getMyListeningStats(PROFILE_TODAY_PERIOD_DAYS)
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
    api
      .getMyListeningByDay(PROFILE_TODAY_PERIOD_DAYS)
      .then((res) => {
        if (cancelled) return
        const pts: SparklinePoint[] = (res.buckets || []).map(
          (b) => ({ date: b.date, value: b.minutes }),
        )
        setTrend(pts)
      })
      .catch(() => {
        if (!cancelled) setTrend([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  const minutes = data?.minutes_listened ?? 0
  const tracks = data?.tracks_listened ?? 0
  const topArtist = data?.top_artists?.[0]
  const topGenre = data?.top_genres?.[0]

  const trendHasData = useMemo(
    () => trend.some((p) => p.value > 0),
    [trend],
  )

  return (
    <div className="listener-stats">
      <div className="listener-stats__header">
        <div className="listener-stats__title">
          {t('profile.listenStats.title', 'Ваше прослушивание')}
        </div>
        <span className="settings-hint">
          {t('profile.listenStats.today', 'Сегодня')}
        </span>
      </div>

      {!loading && trendHasData && (
        <Sparkline
          points={trend}
          ariaLabel={t(
            'profile.listenStats.trendAria',
            'Тренд прослушивания по дням',
          )}
        />
      )}

      {loading ? (
        <StatsRowSkeleton />
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

      {!loading && (minutes > 0 || tracks > 0) && (
        <div className="listener-stats__footer">
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            onClick={() => navigate('/my-top')}
          >
            {t(
              'profile.listenStats.openMyTop',
              'Открыть «Ваш топ» →',
            )}
          </MotionPress>
        </div>
      )}
    </div>
  )
}
