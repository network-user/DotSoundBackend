import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MotionPress } from '@/components/ui/MotionPress'
import { RecapShareCard } from '@/components/Recap/RecapShareCard'
import { RECAP_MOCK_COVERS } from '@/components/Recap/recapMock'
import { api } from '@/lib/api'
import { showIsland } from '@/lib/island'
import { tg } from '@/lib/telegram'

const PERIODS: { id: 7 | 30 | 365; labelKey: string; defaultLabel: string }[] = [
  { id: 7, labelKey: 'profile.listenStats.period_7', defaultLabel: '7 дней' },
  { id: 30, labelKey: 'profile.listenStats.period_30', defaultLabel: '30 дней' },
  { id: 365, labelKey: 'profile.listenStats.period_365', defaultLabel: 'Год' },
]

function formatMinutes(min: number): string {
  if (min < 60) return `${min} мин`
  const h = Math.floor(min / 60)
  const m = min - h * 60
  return m > 0 ? `${h} ч ${m} мин` : `${h} ч`
}

function trackCoverUrl(key: string | null): string {
  if (!key) return ''
  return `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(key)}`
}

interface ListeningStats {
  minutes_listened: number
  tracks_listened: number
  top_artists: { name: string; minutes: number; plays: number }[]
  top_genres: { name: string; minutes: number; plays: number }[]
}

interface ApiTopTrack {
  id: number
  cover_key: string | null
}

export function ProfileStatsTab() {
  const { t } = useTranslation()
  const [period, setPeriod] = useState<7 | 30 | 365>(30)
  const [stats, setStats] = useState<ListeningStats | null>(null)
  const [topTracks, setTopTracks] = useState<ApiTopTrack[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const topWindow =
        period === 7 ? '7d' : period === 30 ? '30d' : '90d'
      const [listenRes, topRes] = await Promise.all([
        api.getMyListeningStats(period),
        api.getMyTop(topWindow as '7d' | '30d' | '90d'),
      ])
      setStats(listenRes as unknown as ListeningStats)
      setTopTracks(
        (topRes.top_tracks as unknown as ApiTopTrack[]).slice(0, 4),
      )
    } catch {
      setStats(null)
      setTopTracks([])
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => {
    void load()
  }, [load])

  const minutes = stats?.minutes_listened ?? 0
  const genres = stats?.top_genres?.slice(0, 6) ?? []
  const artists = stats?.top_artists?.slice(0, 5) ?? []
  const maxGenreMin = genres.reduce((m, g) => Math.max(m, g.minutes), 1)

  const collageSrc: string[] = []
  for (const tr of topTracks) {
    const url = trackCoverUrl(tr.cover_key)
    if (url) collageSrc.push(url)
  }
  while (collageSrc.length < 4) {
    collageSrc.push(
      RECAP_MOCK_COVERS[collageSrc.length] ?? RECAP_MOCK_COVERS[0]!,
    )
  }

  const periodLabel = t(
    period === 7
      ? 'profile.listenStats.period_7'
      : period === 30
        ? 'profile.listenStats.period_30'
        : 'profile.listenStats.period_365',
    period === 7 ? '7 дней' : period === 30 ? '30 дней' : 'Год',
  )

  const handleShare = () => {
    const text = `${minutes} ${t('profile.stats.minutesCaption', 'минут прослушано')} ${t('profile.stats.shareHeadline', 'за')} ${periodLabel} — DotSound`
    if (tg?.shareText) {
      tg.shareText(text)
    } else {
      void navigator.clipboard.writeText(text).then(() => {
        showIsland({ kind: 'toast', title: t('redesign.track.copyDone', 'Скопировано'), durationMs: 2000 })
      })
    }
  }

  return (
    <div className="profile-stats-tab">
      <div className="listener-stats__periods pst-periods">
        {PERIODS.map((p) => (
          <MotionPress
            key={p.id}
            type="button"
            variant="ghost"
            haptic="selection"
            role="tab"
            aria-selected={period === p.id}
            className={`pb-extras-btn${period === p.id ? ' active' : ''}`}
            onClick={() => setPeriod(p.id)}
          >
            {t(p.labelKey, p.defaultLabel)}
          </MotionPress>
        ))}
      </div>

      {loading ? (
        <div className="page-loading">
          {t('common.loading', 'Загрузка…')}
        </div>
      ) : !stats || minutes === 0 ? (
        <div className="page-empty pst-empty">
          {t(
            'profile.stats.empty',
            'Пока недостаточно прослушиваний для статистики.',
          )}
        </div>
      ) : (
        <>
          <div className="pst-hero">
            <div className="pst-hero__value">
              {formatMinutes(minutes)}
            </div>
            <div className="pst-hero__label">
              {t('profile.listenStats.minutes', 'Минуты прослушивания')}
            </div>
          </div>

          {genres.length > 0 && (
            <section className="pst-section">
              <h2 className="pst-section__title">
                {t('profile.stats.genres', 'По жанрам')}
              </h2>
              <ul className="pst-genre-bars">
                {genres.map((g) => (
                  <li key={g.name} className="pst-genre-bar">
                    <span className="pst-genre-bar__name">
                      {g.name}
                    </span>
                    <div className="pst-genre-bar__track">
                      <div
                        className="pst-genre-bar__fill"
                        style={{
                          width: `${(g.minutes / maxGenreMin) * 100}%`,
                        }}
                      />
                    </div>
                    <span className="pst-genre-bar__val">
                      {formatMinutes(g.minutes)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {artists.length > 0 && (
            <section className="pst-section">
              <h2 className="pst-section__title">
                {t('profile.stats.artists', 'Топ исполнители')}
              </h2>
              <ul className="pst-artist-list">
                {artists.map((a, i) => (
                  <li key={a.name} className="pst-artist-row">
                    <span className="pst-artist-row__rank">
                      {i + 1}
                    </span>
                    <span className="pst-artist-row__name">
                      {a.name}
                    </span>
                    <span className="pst-artist-row__val">
                      {formatMinutes(a.minutes)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="pst-section">
            <h2 className="pst-section__title">
              {t('profile.stats.shareTitle', 'Поделиться')}
            </h2>
            <RecapShareCard
              brandLabel=".звук"
              totalMinutes={minutes}
              headline={`${t('profile.stats.shareHeadline', 'За')} ${periodLabel}`}
              minutesCaption={t(
                'profile.stats.minutesCaption',
                'минут прослушано',
              )}
              collageSrc={collageSrc}
              saveLabel={t('profile.stats.save', 'Сохранить')}
              shareLabel={t('profile.stats.share', 'Поделиться')}
              exportTodoHint={t(
                'profile.stats.exportHint',
                'Скоро: сохранение в галерею',
              )}
              onSave={() => {}}
              onShare={handleShare}
            />
          </section>
        </>
      )}
    </div>
  )
}
