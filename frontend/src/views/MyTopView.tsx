import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { ListeningDayChart } from '@/components/Profile/ListeningDayChart'
import { MotionPress } from '@/components/ui/MotionPress'
import { useMatchMedia } from '@/hooks/useMatchMedia'
import { api } from '@/lib/api'
import type { Track } from '@/types/api'

const WINDOWS: Array<{ key: '7d' | '30d' | '90d' | 'all'; labelKey: string }> = [
  { key: '7d', labelKey: 'myTop.window7d' },
  { key: '30d', labelKey: 'myTop.window30d' },
  { key: '90d', labelKey: 'myTop.window90d' },
  { key: 'all', labelKey: 'myTop.windowAll' },
]

interface ApiTopGenre {
  genre: string
  completed_listens: number
}

interface ApiTopTrack {
  id: number
  title: string
  artist: string | null
  play_count: number
  cover_key: string | null
}

const WINDOW_TO_DAYS: Record<
  '7d' | '30d' | '90d' | 'all',
  number
> = {
  '7d': 7,
  '30d': 30,
  '90d': 90,
  all: 90,
}

export function MyTopView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const coarse = useMatchMedia('(pointer: coarse)')
  const genreListRef = useRef<HTMLUListElement>(null)
  const [windowKey, setWindowKey] = useState<
    '7d' | '30d' | '90d' | 'all'
  >('30d')
  const [tracks, setTracks] = useState<ApiTopTrack[]>([])
  const [genres, setGenres] = useState<ApiTopGenre[]>([])
  const [buckets, setBuckets] = useState<
    { date: string; minutes: number }[]
  >([])
  const [loading, setLoading] = useState(false)
  const [peekGenre, setPeekGenre] = useState<string | null>(null)
  const [stickGenre, setStickGenre] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [top, hours] = await Promise.all([
        api.getMyTop(windowKey),
        api.getMyListeningByDay(WINDOW_TO_DAYS[windowKey]),
      ])
      setTracks(top.top_tracks)
      setGenres(top.top_genres)
      setBuckets(hours.buckets)
    } catch {
      setTracks([])
      setGenres([])
      setBuckets([])
    } finally {
      setLoading(false)
    }
  }, [windowKey])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    setPeekGenre(null)
    setStickGenre(null)
  }, [windowKey])

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

  const activeGenre = coarse ? stickGenre : stickGenre ?? peekGenre

  const trackList = useMemo<Track[]>(
    () =>
      tracks.map((t) => ({
        id: t.id,
        title: t.title,
        artist: t.artist,
        play_count: t.play_count,
        cover_key: t.cover_key,
      })) as unknown as Track[],
    [tracks],
  )

  return (
    <div className="my-top-view">
      <header className="my-top-header">
        <MotionPress
          type="button"
          variant="ghost"
          haptic="selection"
          className="my-top-back"
          onClick={() => navigate('/profile')}
        >
          <Icon name="chevron-left" size={18} />
          <span>{t('profile.backToProfile', 'Вернуться в профиль')}</span>
        </MotionPress>
        <h1>{t('myTop.title', 'Ваш топ')}</h1>
        <p className="settings-hint">
          {t(
            'myTop.hint',
            'Топ треков и жанров на основе ваших прослушиваний.',
          )}
        </p>
        <div className="my-top-window-row">
          {WINDOWS.map((w) => (
            <MotionPress
              key={w.key}
              type="button"
              variant={windowKey === w.key ? 'primary' : 'ghost'}
              haptic="light"
              className="chip"
              onClick={() => setWindowKey(w.key)}
            >
              {t(w.labelKey, w.key)}
            </MotionPress>
          ))}
        </div>
      </header>

      {loading ? (
        <div className="page-loading">
          {t('common.loading', 'Загрузка…')}
        </div>
      ) : trackList.length === 0 &&
        genres.length === 0 &&
        buckets.length === 0 ? (
        <div className="page-empty">
          {t(
            'myTop.empty',
            'Пока недостаточно прослушиваний для построения топа.',
          )}
        </div>
      ) : (
        <>
          {buckets.length > 0 ? (
            <section className="my-top-section my-top-hours">
              <h2>
                {t(
                  'myTop.hoursByDay',
                  'Минуты прослушивания по дням',
                )}
              </h2>
              <ListeningDayChart buckets={buckets} />
              <div className="my-top-hours__total settings-hint">
                {t('myTop.hoursTotal', 'Всего: {{m}} мин', {
                  m: buckets.reduce(
                    (s, b) => s + b.minutes,
                    0,
                  ),
                })}
              </div>
            </section>
          ) : null}
          {genres.length > 0 ? (
            <section className="my-top-section my-top-genres">
              <h2>{t('myTop.topGenres', 'Топ жанров')}</h2>
              <ul
                ref={genreListRef}
                className="my-top-genres__list"
                onPointerLeave={() => setPeekGenre(null)}
              >
                {genres.map((g) => (
                  <li
                    key={g.genre}
                    className={`my-top-genres__item${
                      g.genre === activeGenre ? ' is-active' : ''
                    }${
                      activeGenre && g.genre !== activeGenre
                        ? ' is-dimmed'
                        : ''
                    }`}
                    onPointerEnter={() => {
                      if (!coarse) setPeekGenre(g.genre)
                    }}
                    onPointerDown={(ev) => {
                      if (!coarse) return
                      ev.preventDefault()
                      setStickGenre((cur) =>
                        cur === g.genre ? null : g.genre,
                      )
                    }}
                  >
                    <span>{g.genre}</span>
                    <span className="settings-hint">
                      {g.completed_listens}
                    </span>
                  </li>
                ))}
              </ul>
              {activeGenre ? (
                <div
                  className="my-top-genres__callout"
                  aria-live="polite"
                >
                  {(() => {
                    const g = genres.find(
                      (x) => x.genre === activeGenre,
                    )
                    if (!g) return null
                    return (
                      <span>
                        {t(
                          'myTop.genreRowDetail',
                          '{{genre}} · {{plays}} completed listens',
                          {
                            genre: g.genre,
                            plays: g.completed_listens,
                          },
                        )}
                      </span>
                    )
                  })()}
                </div>
              ) : null}
            </section>
          ) : null}
          {trackList.length > 0 ? (
            <section className="my-top-section">
              <h2>{t('myTop.topTracks', 'Топ треков')}</h2>
              <TrackList tracks={trackList} />
            </section>
          ) : null}
        </>
      )}
    </div>
  )
}
