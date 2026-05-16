import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { AnimatePresence } from 'framer-motion'
import { m, useReducedMotion } from '@/lib/motion'
import { MotionPress } from '@/components/ui/MotionPress'
import { RecapShareCard } from '@/components/Recap/RecapShareCard'
import { RECAP_MOCK_COVERS } from '@/components/Recap/recapMock'
import { ListeningDayChart } from '@/components/Profile/ListeningDayChart'
import type { ListeningDayBucket } from '@/components/Profile/ListeningDayChart'
import { useMatchMedia } from '@/hooks/useMatchMedia'
import { api } from '@/lib/api'
import { showIsland } from '@/lib/island'
import { tg } from '@/lib/telegram'
import { createSharePoster, downloadBlob } from '@/lib/shareCard'
import { coverProxyUrl } from '@/lib/coverProxy'

const PERIODS: { id: 7 | 30 | 365; labelKey: string; defaultLabel: string }[] =
  [
    {
      id: 7,
      labelKey: 'profile.listenStats.period_7',
      defaultLabel: '7 дней',
    },
    {
      id: 30,
      labelKey: 'profile.listenStats.period_30',
      defaultLabel: '30 дней',
    },
    {
      id: 365,
      labelKey: 'profile.listenStats.period_365',
      defaultLabel: 'Год',
    },
  ]

function formatMinutes(min: number): string {
  if (min < 60) return `${min} мин`
  const h = Math.floor(min / 60)
  const m = min - h * 60
  return m > 0 ? `${h} ч ${m} мин` : `${h} ч`
}

function trackCoverUrl(key: string | null): string {
  if (!key) return ''
  return coverProxyUrl(key, { width: 240 })
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
  const reduce = useReducedMotion()
  const coarse = useMatchMedia('(pointer: coarse)')
  const genreListRef = useRef<HTMLUListElement>(null)
  const artistListRef = useRef<HTMLUListElement>(null)
  const [period, setPeriod] = useState<7 | 30 | 365>(30)
  const [stats, setStats] = useState<ListeningStats | null>(null)
  const [buckets, setBuckets] = useState<ListeningDayBucket[]>([])
  const [topTracks, setTopTracks] = useState<ApiTopTrack[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [peekGenre, setPeekGenre] = useState<string | null>(null)
  const [stickGenre, setStickGenre] = useState<string | null>(null)
  const [peekArtist, setPeekArtist] = useState<string | null>(null)
  const [stickArtist, setStickArtist] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const topWindow =
        period === 7 ? '7d' : period === 30 ? '30d' : '90d'
      const [listenRes, topRes, dayRes] = await Promise.all([
        api.getMyListeningStats(period),
        api.getMyTop(topWindow as '7d' | '30d' | '90d'),
        api.getMyListeningByDay(period === 365 ? 90 : period),
      ])
      setStats(listenRes as unknown as ListeningStats)
      setTopTracks(
        (topRes.top_tracks as unknown as ApiTopTrack[]).slice(0, 4),
      )
      setBuckets((dayRes.buckets as ListeningDayBucket[]) ?? [])
    } catch {
      setStats(null)
      setTopTracks([])
      setBuckets([])
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!coarse || !stickGenre) return
    const fn = (ev: PointerEvent) => {
      if (!genreListRef.current?.contains(ev.target as Node)) {
        setStickGenre(null)
      }
    }
    document.addEventListener('pointerdown', fn, true)
    return () => document.removeEventListener('pointerdown', fn, true)
  }, [coarse, stickGenre])

  useEffect(() => {
    if (!coarse || !stickArtist) return
    const fn = (ev: PointerEvent) => {
      if (!artistListRef.current?.contains(ev.target as Node)) {
        setStickArtist(null)
      }
    }
    document.addEventListener('pointerdown', fn, true)
    return () => document.removeEventListener('pointerdown', fn, true)
  }, [coarse, stickArtist])

  useEffect(() => {
    setPeekGenre(null)
    setStickGenre(null)
    setPeekArtist(null)
    setStickArtist(null)
  }, [period])

  const activeGenreName = coarse ? stickGenre : stickGenre ?? peekGenre
  const activeArtistName = coarse ? stickArtist : stickArtist ?? peekArtist

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
  const headline = `${t('profile.stats.shareHeadline', 'За')} ${periodLabel}`
  const minutesCaption = t(
    'profile.stats.minutesCaption',
    'минут прослушано',
  )

  const handleShare = () => {
    const text = `${minutes} ${minutesCaption} ${headline} — DotSound`
    const shareText = (tg as unknown as {
      shareText?: (t: string) => void
    } | undefined)?.shareText
    if (shareText) {
      shareText(text)
    } else {
      void navigator.clipboard.writeText(text).then(() => {
        showIsland({
          kind: 'toast',
          title: t('redesign.track.copyDone', 'Скопировано'),
          durationMs: 2000,
        })
      })
    }
  }

  const handleSave = async () => {
    if (saving) return
    setSaving(true)
    try {
      const blob = await createSharePoster({
        totalMinutes: minutes,
        headline,
        minutesCaption,
        brandLabel: '.звук',
        collageSrc,
      })
      if (blob) {
        downloadBlob(blob, 'dotsound-stats.png')
      }
    } finally {
      setSaving(false)
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
              {t(
                'profile.listenStats.minutes',
                'Минуты прослушивания',
              )}
            </div>
          </div>

          {/* Listening sparkline */}
          {buckets.length > 0 && (
            <section className="my-top-hours pst-section">
              <h2 className="pst-section__title">
                {t(
                  'myTop.hoursByDay',
                  'Минуты прослушивания по дням',
                )}
              </h2>
              <ListeningDayChart buckets={buckets} />
            </section>
          )}

          {/* Genre bars with AnimatePresence on period change */}
          {genres.length > 0 && (
            <section className="pst-section">
              <h2 className="pst-section__title">
                {t('profile.stats.genres', 'По жанрам')}
              </h2>
              <AnimatePresence mode="wait" initial={false}>
                <m.ul
                  ref={genreListRef}
                  key={period}
                  className="pst-genre-bars"
                  initial={reduce ? { opacity: 1 } : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={reduce ? { opacity: 1 } : { opacity: 0 }}
                  transition={{ duration: 0.18 }}
                  onPointerLeave={() => setPeekGenre(null)}
                >
                  {genres.map((g, i) => (
                    <m.li
                      key={g.name}
                      className={`pst-genre-bar${
                        g.name === activeGenreName
                          ? ' is-active'
                          : ''
                      }${
                        activeGenreName && g.name !== activeGenreName
                          ? ' is-dimmed'
                          : ''
                      }`}
                      initial={
                        reduce ? {} : { opacity: 0, x: -6 }
                      }
                      animate={{ opacity: 1, x: 0 }}
                      transition={{
                        duration: 0.22,
                        delay: reduce ? 0 : i * 0.04,
                      }}
                      onPointerEnter={() => {
                        if (!coarse) setPeekGenre(g.name)
                      }}
                      onPointerDown={(ev) => {
                        if (!coarse) return
                        ev.preventDefault()
                        setStickGenre((cur) =>
                          cur === g.name ? null : g.name,
                        )
                      }}
                    >
                      <span className="pst-genre-bar__name">
                        {g.name}
                      </span>
                      <div className="pst-genre-bar__track">
                        <m.div
                          className="pst-genre-bar__fill"
                          initial={reduce ? undefined : { width: 0 }}
                          animate={{
                            width: `${(g.minutes / maxGenreMin) * 100}%`,
                          }}
                          transition={{
                            duration: 0.4,
                            delay: reduce ? 0 : i * 0.04 + 0.1,
                            ease: 'easeOut',
                          }}
                        />
                      </div>
                      <span className="pst-genre-bar__val">
                        {formatMinutes(g.minutes)}
                      </span>
                    </m.li>
                  ))}
                </m.ul>
              </AnimatePresence>
              {activeGenreName ? (
                <div
                  className="pst-interactive-callout"
                  aria-live="polite"
                >
                  {(() => {
                    const g = genres.find(
                      (x) => x.name === activeGenreName,
                    )
                    if (!g) return null
                    return (
                      <span>
                        {t(
                          'profile.stats.genreStemDetail',
                          '{{name}} · {{duration}} · {{plays}} plays',
                          {
                            name: g.name,
                            duration: formatMinutes(g.minutes),
                            plays: g.plays,
                          },
                        )}
                      </span>
                    )
                  })()}
                </div>
              ) : null}
            </section>
          )}

          {/* Top artists */}
          {artists.length > 0 && (
            <section className="pst-section">
              <h2 className="pst-section__title">
                {t('profile.stats.artists', 'Топ исполнители')}
              </h2>
              <ul
                ref={artistListRef}
                className="pst-artist-list"
                onPointerLeave={() => setPeekArtist(null)}
              >
                {artists.map((a, i) => (
                  <li
                    key={a.name}
                    className={`pst-artist-row${
                      a.name === activeArtistName
                        ? ' is-active'
                        : ''
                    }${
                      activeArtistName && a.name !== activeArtistName
                        ? ' is-dimmed'
                        : ''
                    }`}
                    onPointerEnter={() => {
                      if (!coarse) setPeekArtist(a.name)
                    }}
                    onPointerDown={(ev) => {
                      if (!coarse) return
                      ev.preventDefault()
                      setStickArtist((cur) =>
                        cur === a.name ? null : a.name,
                      )
                    }}
                  >
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
              {activeArtistName ? (
                <div
                  className="pst-interactive-callout"
                  aria-live="polite"
                >
                  {(() => {
                    const a = artists.find(
                      (x) => x.name === activeArtistName,
                    )
                    if (!a) return null
                    return (
                      <span>
                        {t(
                          'profile.stats.artistStemDetail',
                          '{{name}} · {{duration}} · {{plays}} plays',
                          {
                            name: a.name,
                            duration: formatMinutes(a.minutes),
                            plays: a.plays,
                          },
                        )}
                      </span>
                    )
                  })()}
                </div>
              ) : null}
            </section>
          )}

          {/* Share card */}
          <section className="pst-section">
            <h2 className="pst-section__title">
              {t('profile.stats.shareTitle', 'Поделиться')}
            </h2>
            <RecapShareCard
              brandLabel=".звук"
              totalMinutes={minutes}
              headline={headline}
              minutesCaption={minutesCaption}
              collageSrc={collageSrc}
              saveLabel={
                saving
                  ? t('common.loading', 'Загрузка…')
                  : t('profile.stats.save', 'Сохранить')
              }
              shareLabel={t('profile.stats.share', 'Поделиться')}
              exportTodoHint=""
              onSave={() => void handleSave()}
              onShare={handleShare}
            />
          </section>
        </>
      )}
    </div>
  )
}
