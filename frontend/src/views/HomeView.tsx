import {
  type KeyboardEvent,
  useCallback,
  useEffect,
  type RefObject,
  useRef,
  useState,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { useToast } from '@/components/ui/Toast'
import { Icon } from '@/components/Icon/Icon'
import { NotificationBell } from '@/components/Notifications/NotificationBell'
import { api, getApiErrorMessage } from '@/lib/api'
import { getInternalUserId } from '@/lib/telegram'
import { useBrandLabel } from '@/lib/brand'
import { usePlayerActions } from '@/store/PlayerContext'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import { trackActivationEvent } from '@/lib/activation'
import { usePullToRefresh } from '@/hooks/usePullToRefresh'
import type {
  FollowedArtistItem,
  GenreMixItem,
  Track,
  UserResponse,
} from '@/types/api'

interface HomeSection {
  title: string
  section_type: string
  tracks: Track[]
}

function timeGreeting(): string {
  const h = new Date().getHours()
  return h < 18 ? 'Добрый день' : 'Добрый вечер'
}

function coverUrl(key: string | null): string | null {
  if (!key) return null
  return `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(key)}`
}

interface TrackTileProps {
  track: Track
  onPlay: (t: Track) => void
}

function TrackTile({ track, onPlay }: TrackTileProps) {
  const src = coverUrl(track.cover_key)
  return (
    <button
      type="button"
      className="home-track-tile"
      onClick={() => onPlay(track)}
      title={[track.title, track.artist].filter(Boolean).join(' — ')}
    >
      <div className="home-track-tile__cover">
        {src ? (
          <img
            src={src}
            alt=""
            width={112}
            height={112}
            loading="lazy"
            decoding="async"
          />
        ) : (
          <div className="home-track-tile__cover-placeholder">
            <Icon name="music" size={28} />
          </div>
        )}
      </div>
      <div className="home-track-tile__title">
        {track.title || 'Без названия'}
      </div>
      {track.artist && (
        <div className="home-track-tile__artist">
          {track.artist}
        </div>
      )}
    </button>
  )
}

interface SectionProps {
  title: string
  onMore?: () => void
  tracks: Track[]
  onPlay: (t: Track) => void
}

interface FeaturedCardProps {
  track: Track
  label: string
  reason?: string | null
  heroImageKey?: string | null
  brandLabel: string
  onPlay: (t: Track) => void
  onStartRadio?: (t: Track) => void
  showRadioCta?: boolean
}

function FeaturedCard({
  track,
  label,
  reason,
  heroImageKey,
  brandLabel,
  onPlay,
  onStartRadio,
  showRadioCta,
}: FeaturedCardProps) {
  const src = coverUrl(heroImageKey || track.cover_key)
  const handleMainKeyDown = (
    e: KeyboardEvent<HTMLDivElement>,
  ) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onPlay(track)
    }
  }
  return (
    <div className="home-featured-card">
      <div
        role="button"
        tabIndex={0}
        className="home-featured__main"
        onClick={() => onPlay(track)}
        onKeyDown={handleMainKeyDown}
      >
        <div className="home-featured__copy">
          <span className="home-featured__eyebrow">{label}</span>
          <button
            type="button"
            className="home-featured__play"
            onClick={(e) => {
              e.stopPropagation()
              onPlay(track)
            }}
            aria-label={`Слушать ${track.title || 'трек'}`}
          >
            <Icon name="play" size={18} />
            <span>Play</span>
          </button>
          <strong className="home-featured__title">
            {track.title || 'Без названия'}
          </strong>
          <span className="home-featured__artist">
            {reason || track.artist || brandLabel}
          </span>
          {showRadioCta && onStartRadio && (
            <button
              type="button"
              className="home-featured__radio"
              onClick={(e) => {
                e.stopPropagation()
                onStartRadio(track)
              }}
              aria-label="Запустить бесконечную волну на основе трека"
            >
              <Icon name="radio" size={14} />
              <span>Бесконечная волна</span>
            </button>
          )}
        </div>
        <div className="home-featured__cover">
          {src ? (
            <img
              src={src}
              alt=""
              width={132}
              height={132}
              decoding="async"
            />
          ) : (
            <Icon name="music" size={36} />
          )}
        </div>
      </div>
    </div>
  )
}

function CarouselDots({
  count,
  containerRef,
}: {
  count: number
  containerRef: RefObject<HTMLElement>
}) {
  const dotCount = Math.min(4, Math.ceil(count / 2))
  const [active, setActive] = useState(0)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const update = () => {
      const maxScroll = Math.max(
        0,
        el.scrollWidth - el.clientWidth,
      )
      if (maxScroll <= 0 || dotCount <= 1) {
        setActive(0)
        return
      }
      const ratio = el.scrollLeft / maxScroll
      const idx = Math.round(ratio * (dotCount - 1))
      setActive(Math.max(0, Math.min(dotCount - 1, idx)))
    }

    const onScroll = () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
      }
      rafRef.current = requestAnimationFrame(update)
    }

    update()
    el.addEventListener('scroll', onScroll, {
      passive: true,
    })
    window.addEventListener('resize', update)
    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
      }
      el.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', update)
    }
  }, [containerRef, dotCount])

  if (dotCount < 2) return null

  const scrollToDot = (idx: number) => {
    const el = containerRef.current
    if (!el) return
    const maxScroll = Math.max(
      0,
      el.scrollWidth - el.clientWidth,
    )
    if (maxScroll <= 0) return
    const left =
      dotCount === 1
        ? 0
        : (maxScroll * idx) / (dotCount - 1)
    el.scrollTo({ left, behavior: 'smooth' })
  }

  return (
    <div className="home-carousel-dots">
      {Array.from({ length: dotCount }).map((_, i) => (
        <button
          key={i}
          type="button"
          className={`home-carousel-dot${i === active ? ' active' : ''}`}
          onClick={() => scrollToDot(i)}
          aria-label={`Slide ${i + 1}`}
          aria-current={i === active ? 'true' : undefined}
        />
      ))}
    </div>
  )
}

function CarouselArrows({
  containerRef,
}: {
  containerRef: RefObject<HTMLElement>
}) {
  const [canLeft, setCanLeft] = useState(false)
  const [canRight, setCanRight] = useState(false)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const update = () => {
      const maxScroll = Math.max(
        0,
        el.scrollWidth - el.clientWidth,
      )
      if (maxScroll <= 1) {
        setCanLeft(false)
        setCanRight(false)
        return
      }
      setCanLeft(el.scrollLeft > 2)
      setCanRight(el.scrollLeft < maxScroll - 2)
    }

    const onScroll = () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
      }
      rafRef.current = requestAnimationFrame(update)
    }

    update()
    el.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', update)
    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
      }
      el.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', update)
    }
  }, [containerRef])

  const scrollByPage = (direction: -1 | 1) => {
    const el = containerRef.current
    if (!el) return
    const distance = Math.max(
      180,
      Math.round(el.clientWidth * 0.8),
    )
    el.scrollBy({
      left: distance * direction,
      behavior: 'smooth',
    })
  }

  if (!canLeft && !canRight) return null

  return (
    <>
      {canLeft && (
        <button
          type="button"
          className="home-carousel-arrow home-carousel-arrow--left"
          onClick={() => scrollByPage(-1)}
          aria-label="Прокрутить влево"
        >
          <Icon
            name="chevron"
            size={20}
            className="home-carousel-arrow__icon home-carousel-arrow__icon--left"
          />
        </button>
      )}
      {canRight && (
        <button
          type="button"
          className="home-carousel-arrow home-carousel-arrow--right"
          onClick={() => scrollByPage(1)}
          aria-label="Прокрутить вправо"
        >
          <Icon
            name="chevron"
            size={20}
            className="home-carousel-arrow__icon"
          />
        </button>
      )}
    </>
  )
}

function TrackCarouselSection({
  title,
  onMore,
  tracks,
  onPlay,
}: SectionProps) {
  const carouselRef =
    useRef<HTMLDivElement>(null)
  if (!tracks.length) return null
  return (
    <div>
      <div className="home-section-header">
        <span className="home-section-header__title">{title}</span>
        {onMore && (
          <button
            type="button"
            className="home-section-header__link"
            onClick={onMore}
          >
            Все
          </button>
        )}
      </div>
      <div className="home-carousel-shell">
        <div ref={carouselRef} className="home-carousel">
          {tracks.map((t) => (
            <TrackTile key={t.id} track={t} onPlay={onPlay} />
          ))}
        </div>
        <CarouselArrows containerRef={carouselRef} />
      </div>
      <CarouselDots
        count={tracks.length}
        containerRef={carouselRef}
      />
    </div>
  )
}

interface GenreCardProps {
  mix: GenreMixItem
  onPlay: (tracks: Track[]) => void
  onOpen: () => void
}

function GenreMixCard({ mix, onPlay, onOpen }: GenreCardProps) {
  const covers = mix.tracks
    .slice(0, 4)
    .map((t) => coverUrl(t.cover_key))
    .filter(Boolean) as string[]

  const handleCardKeyDown = (
    e: KeyboardEvent<HTMLDivElement>,
  ) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onOpen()
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      className="home-genre-mix-card"
      onClick={onOpen}
      onKeyDown={handleCardKeyDown}
      title={mix.title}
    >
      <div className="home-genre-mix-card__mosaic">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="home-genre-mix-card__mosaic-cell">
            {covers[i] && (
              <img
                src={covers[i]}
                alt=""
                loading="lazy"
                decoding="async"
              />
            )}
          </div>
        ))}
      </div>
      <div className="home-genre-mix-card__overlay" />
      <button
        type="button"
        className="home-genre-mix-card__play"
        onClick={(e) => {
          e.stopPropagation()
          if (mix.tracks.length) onPlay(mix.tracks)
        }}
        aria-label={`Слушать ${mix.title}`}
      >
        <Icon name="play" size={14} />
      </button>
      <span className="home-genre-mix-card__genre">
        {mix.genre.charAt(0).toUpperCase() + mix.genre.slice(1)}
      </span>
      <span className="home-genre-mix-card__count">
        {mix.tracks.length} треков
      </span>
    </div>
  )
}

function SkeletonBlock({ className }: { className: string }) {
  return <div className={`skeleton ${className}`} />
}

const QUICK_ITEMS: {
  label: string
  icon: string
  path: string
}[] = [
  { label: 'Плейлист дня', icon: 'calendar', path: '/daily-mix' },
  { label: 'Плейлист недели', icon: 'star', path: '/weekly-mix' },
  { label: 'Топ недели', icon: 'flame', path: '/weekly-top' },
  { label: 'Выбор пользователей', icon: 'heart', path: '/user-choice' },
  { label: 'Библиотека', icon: 'layers', path: '/library' },
  { label: 'Радио', icon: 'radio', path: '/radio' },
  { label: 'Подписки', icon: 'users-following', path: '/library?tab=following' },
]

interface HomeViewProps {
  onOpenArtist?: (id: number) => void
}

export function HomeView({ onOpenArtist }: HomeViewProps) {
  const navigate = useNavigate()
  const toast = useToast()
  const { playTrack, startRadio } = usePlayerActions()
  const brandLabel = useBrandLabel()

  const [me, setMe] = useState<UserResponse | null>(null)
  const [sections, setSections] = useState<HomeSection[] | null>(null)
  const [genreMixes, setGenreMixes] = useState<GenreMixItem[] | null>(null)
  const [followedArtists, setFollowedArtists] = useState<
    FollowedArtistItem[] | null
  >(null)
  const [recentlyPlayed, setRecentlyPlayed] = useState<Track[] | null>(null)
  const [fallbackTracks, setFallbackTracks] = useState<Track[] | null>(null)
  const genreRowRef =
    useRef<HTMLDivElement>(null)
  const artistRowRef =
    useRef<HTMLDivElement>(null)

  useEffect(() => {
    const uid = getInternalUserId()
    if (uid) {
      api.getUserProfile(uid).then(setMe).catch(() => {})
    }

    api
      .getHomeRecommendations()
      .then((data) => {
        setSections(data.sections)
      })
      .catch(() => {
        api
          .getTracks({ size: 50 })
          .then((data) => setFallbackTracks(data.items))
          .catch(() => setFallbackTracks([]))
      })

    api
      .getGenreMixes()
      .then((data) => setGenreMixes(data.mixes))
      .catch(() => setGenreMixes([]))

    api
      .getFollowedArtistsList(30)
      .then((data) => setFollowedArtists(data.items))
      .catch(() => setFollowedArtists([]))

    api
      .getListenHistory(20)
      .then((data) => setRecentlyPlayed(data.items))
      .catch(() => setRecentlyPlayed([]))
  }, [])

  const handleRefresh = useCallback(async () => {
    setSections(null)
    setGenreMixes(null)
    setFollowedArtists(null)
    setRecentlyPlayed(null)
    await Promise.allSettled([
      api
        .getHomeRecommendations()
        .then((data) => setSections(data.sections))
        .catch(() => {
          setFallbackTracks([])
        }),
      api
        .getGenreMixes()
        .then((data) => setGenreMixes(data.mixes))
        .catch(() => setGenreMixes([])),
      api
        .getFollowedArtistsList(30)
        .then((data) => setFollowedArtists(data.items))
        .catch(() => setFollowedArtists([])),
      api
        .getListenHistory(20)
        .then((data) => setRecentlyPlayed(data.items))
        .catch(() => setRecentlyPlayed([])),
    ])
  }, [])

  const pull = usePullToRefresh({
    onRefresh: handleRefresh,
    enabled: true,
  })

  const homeFirstTracks = (sections ?? [])
    .flatMap((s) => s.tracks.slice(0, 1))
    .slice(0, 6)
  usePrefetchTracks(homeFirstTracks, 'home')

  useEffect(() => {
    const main = document.getElementById('main')
    if (!main) return
    const saved = sessionStorage.getItem('home-scroll')
    if (saved) {
      const y = Number(saved)
      if (Number.isFinite(y) && y > 0) {
        requestAnimationFrame(() => {
          main.scrollTop = y
        })
      }
    }
    let raf = 0
    const onScroll = () => {
      if (raf) return
      raf = requestAnimationFrame(() => {
        raf = 0
        try {
          sessionStorage.setItem(
            'home-scroll',
            String(Math.round(main.scrollTop)),
          )
        } catch {
          // quota / privacy mode; ignore
        }
      })
    }
    main.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      if (raf) cancelAnimationFrame(raf)
      main.removeEventListener('scroll', onScroll)
    }
  }, [])

  const handlePlay = useCallback(
    async (track: Track) => {
      try {
        await playTrack(track)
        trackActivationEvent('home_first_play')
      } catch (e) {
        toast.error(getApiErrorMessage(e, 'Ошибка воспроизведения'))
      }
    },
    [playTrack, toast],
  )

  const handlePlayAll = useCallback(
    async (tracks: Track[]) => {
      if (!tracks.length) return
      try {
        await playTrack(tracks[0])
        trackActivationEvent('home_play_all')
      } catch (e) {
        toast.error(getApiErrorMessage(e, 'Ошибка воспроизведения'))
      }
    },
    [playTrack, toast],
  )

  const handleStartRadio = useCallback(
    async (track: Track) => {
      try {
        await startRadio(track)
        trackActivationEvent('home_start_radio')
      } catch (e) {
        toast.error(getApiErrorMessage(e, 'Не удалось запустить волну'))
      }
    },
    [startRadio, toast],
  )

  const handleStartFirstSession = useCallback(async () => {
    const candidates: Track[] = []
    if (sections) {
      const order = [
        'continue',
        'personalized',
        'user_choice',
        'new_releases',
        'genre_popular',
        'fav_artists',
        'popular',
      ]
      for (const key of order) {
        const section = sections.find(
          (s) => s.section_type === key,
        )
        if (section?.tracks?.length) {
          candidates.push(...section.tracks)
          break
        }
      }
    }
    if (!candidates.length && genreMixes && genreMixes.length) {
      candidates.push(...genreMixes[0].tracks)
    }
    if (!candidates.length && fallbackTracks?.length) {
      candidates.push(...fallbackTracks)
    }
    if (!candidates.length) {
      try {
        const data = await api.getTracks({ size: 30 })
        candidates.push(...data.items)
      } catch {
        toast.error('Пока нет треков для запуска')
        return
      }
    }
    if (!candidates.length) {
      toast.info('Пока нет треков — попробуйте позже')
      return
    }
    try {
      await startRadio(candidates[0])
      trackActivationEvent('home_first_session_start')
    } catch (e) {
      toast.error(getApiErrorMessage(e, 'Не удалось запустить'))
    }
  }, [sections, fallbackTracks, genreMixes, startRadio, toast])

  const greeting = timeGreeting()
  const displayName =
    me?.display_name ||
    me?.first_name ||
    me?.username ||
    null

  const sectionMap = new Map<string, HomeSection>()
  if (sections) {
    for (const s of sections) {
      sectionMap.set(s.section_type, s)
    }
  }
  const featuredSource =
    sectionMap.get('continue') ||
    sectionMap.get('personalized') ||
    sectionMap.get('user_choice') ||
    sectionMap.get('popular')
  const featuredTrack =
    featuredSource?.tracks[0] ||
    fallbackTracks?.[0] ||
    null
  const featuredLabel =
    featuredSource?.section_type === 'continue'
      ? 'Продолжить'
      : featuredSource?.section_type === 'user_choice'
        ? 'Выбор пользователей'
        : brandLabel
  const loadingFeatured =
    sections === null && fallbackTracks === null

  return (
    <section id="view-home" className="view active">
      {(pull.pulling || pull.refreshing) && (
        <div
          className="ptr-indicator"
          aria-live="polite"
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: pull.refreshing
              ? 36
              : Math.min(72, Math.round(pull.distance)),
            opacity: pull.refreshing ? 1 : Math.min(1, pull.distance / 70),
            color: 'var(--clr-text-secondary, rgba(255,255,255,0.7))',
            fontSize: 12,
            transition: pull.refreshing
              ? 'height .15s ease'
              : 'none',
            pointerEvents: 'none',
          }}
        >
          {pull.refreshing ? '↻ Обновляем…' : '↓ Потяните'}
        </div>
      )}
      {/* Greeting */}
      <div className="home-greeting">
        <div className="home-greeting__text">
          <div className="home-greeting__label">
            {displayName
              ? `${greeting} | ${displayName}`
              : greeting}
          </div>
          <div className="home-greeting__sub">{brandLabel}</div>
        </div>
        <NotificationBell />
      </div>

      {featuredTrack ? (
        <FeaturedCard
          track={featuredTrack}
          label={featuredLabel}
          brandLabel={brandLabel}
          onPlay={handlePlay}
          onStartRadio={handleStartRadio}
          showRadioCta={true}
        />
      ) : loadingFeatured ? (
        <div className="home-featured home-featured--skeleton">
          <SkeletonBlock className="home-featured__skeleton-copy" />
          <SkeletonBlock className="home-featured__skeleton-cover" />
        </div>
      ) : null}

      {/* Quick access grid */}
      <div className="home-quick-grid">
        {QUICK_ITEMS.map((item) => (
          <button
            key={item.path}
            type="button"
            className="home-quick-item"
            onClick={() => navigate(item.path)}
          >
            <span className="home-quick-item__icon" aria-hidden>
              <Icon name={item.icon} size={16} />
            </span>
            <span className="home-quick-item__label">
              {item.label}
            </span>
          </button>
        ))}
      </div>

      {/* Genre mixes row */}
      {genreMixes === null ? (
        <div>
          <div className="home-section-header">
            <span className="home-section-header__title">Миксы по жанрам</span>
          </div>
          <div className="home-genre-mix-row home-skeleton-row">
            {[1, 2, 3].map((i) => (
              <SkeletonBlock key={i} className="home-skeleton-mix" />
            ))}
          </div>
        </div>
      ) : genreMixes.length > 0 ? (
        <div>
          <div className="home-section-header">
            <span className="home-section-header__title">Миксы по жанрам</span>
          </div>
          <div className="home-carousel-shell">
            <div ref={genreRowRef} className="home-genre-mix-row">
              {genreMixes.map((mix) => (
                <GenreMixCard
                  key={mix.genre}
                  mix={mix}
                  onPlay={handlePlayAll}
                  onOpen={() =>
                    navigate(
                      `/genre-mix/${encodeURIComponent(mix.genre)}`,
                    )
                  }
                />
              ))}
            </div>
            <CarouselArrows containerRef={genreRowRef} />
          </div>
          <CarouselDots
            count={genreMixes.length}
            containerRef={genreRowRef}
          />
        </div>
      ) : null}

      {/* Continue listening */}
      {sections === null ? (
        <div>
          <div className="home-section-header">
            <span className="home-section-header__title">Продолжить</span>
          </div>
          <div className="home-carousel home-skeleton-row">
            {[1, 2, 3, 4].map((i) => (
              <SkeletonBlock key={i} className="home-skeleton-tile" />
            ))}
          </div>
        </div>
      ) : (
        sectionMap.get('continue') && (
          <TrackCarouselSection
            title={sectionMap.get('continue')!.title}
            tracks={sectionMap.get('continue')!.tracks}
            onPlay={handlePlay}
          />
        )
      )}

      {/* Recently played */}
      {recentlyPlayed === null ? (
        <div>
          <div className="home-section-header">
            <span className="home-section-header__title">Недавно слушали</span>
          </div>
          <div className="home-carousel home-skeleton-row">
            {[1, 2, 3, 4].map((i) => (
              <SkeletonBlock key={i} className="home-skeleton-tile" />
            ))}
          </div>
        </div>
      ) : (() => {
        const continueIds = new Set(
          (sectionMap.get('continue')?.tracks ?? []).map((t) => t.id),
        )
        const recent = recentlyPlayed.filter(
          (t) => !continueIds.has(t.id),
        )
        if (recent.length === 0) return null
        return (
          <TrackCarouselSection
            title="Недавно слушали"
            tracks={recent}
            onPlay={handlePlay}
          />
        )
      })()}

      {/* Followed artists strip */}
      {followedArtists === null ? (
        <div>
          <div className="home-section-header">
            <span className="home-section-header__title">Подписки</span>
          </div>
          <div className="home-artist-strip">
            {[1, 2, 3, 4, 5].map((i) => (
              <SkeletonBlock key={i} className="home-skeleton-chip" />
            ))}
          </div>
        </div>
      ) : followedArtists.length > 0 ? (
        <div>
          <div className="home-section-header">
            <span className="home-section-header__title">Подписки</span>
          </div>
          <div className="home-carousel-shell">
            <div ref={artistRowRef} className="home-artist-strip">
              {followedArtists.map((artist) => {
                const src = coverUrl(artist.image_key)
                return (
                  <button
                    key={artist.id}
                    type="button"
                    className="home-artist-chip"
                    onClick={() => {
                      if (onOpenArtist) {
                        onOpenArtist(artist.id)
                        return
                      }
                      navigate(
                        `/search?q=${encodeURIComponent(artist.name)}`,
                      )
                    }}
                    title={artist.name}
                  >
                    <div className="home-artist-chip__avatar">
                      {src ? (
                        <img
                          src={src}
                          alt=""
                          width={64}
                          height={64}
                          loading="lazy"
                          decoding="async"
                        />
                      ) : (
                        <div className="home-artist-chip__avatar-placeholder">
                          <Icon name="user" size={24} />
                        </div>
                      )}
                    </div>
                    <span className="home-artist-chip__name">
                      {artist.name}
                    </span>
                  </button>
                )
              })}
            </div>
            <CarouselArrows containerRef={artistRowRef} />
          </div>
        </div>
      ) : null}

      {/* Personalized / For You */}
      {sections &&
        sectionMap.get('personalized') && (
          <TrackCarouselSection
            title={sectionMap.get('personalized')!.title}
            tracks={sectionMap.get('personalized')!.tracks}
            onPlay={handlePlay}
          />
        )}

      {/* New releases */}
      {sections &&
        sectionMap.get('new_releases') && (
          <TrackCarouselSection
            title={sectionMap.get('new_releases')!.title}
            tracks={sectionMap.get('new_releases')!.tracks}
            onPlay={handlePlay}
            onMore={() => navigate('/search')}
          />
        )}

      {/* Genre popular */}
      {sections &&
        sectionMap.get('genre_popular') && (
          <TrackCarouselSection
            title={sectionMap.get('genre_popular')!.title}
            tracks={sectionMap.get('genre_popular')!.tracks}
            onPlay={handlePlay}
          />
        )}

      {/* User choice */}
      {sections &&
        sectionMap.get('user_choice') && (
          <TrackCarouselSection
            title={sectionMap.get('user_choice')!.title}
            tracks={sectionMap.get('user_choice')!.tracks}
            onPlay={handlePlay}
            onMore={() => navigate('/user-choice')}
          />
        )}

      {/* Favourite artists */}
      {sections &&
        sectionMap.get('fav_artists') && (
          <TrackCarouselSection
            title={sectionMap.get('fav_artists')!.title}
            tracks={sectionMap.get('fav_artists')!.tracks}
            onPlay={handlePlay}
          />
        )}

      {/* Popular fallback */}
      {sections &&
        sectionMap.get('popular') && (
          <TrackCarouselSection
            title={sectionMap.get('popular')!.title}
            tracks={sectionMap.get('popular')!.tracks}
            onPlay={handlePlay}
          />
        )}

      {/* Fallback flat list if API failed */}
      {!sections && fallbackTracks !== null && fallbackTracks.length > 0 && (
        <div>
          <div className="home-section-header">
            <span className="home-section-header__title">Треки</span>
          </div>
          <div className="home-carousel">
            {fallbackTracks.map((t) => (
              <TrackTile key={t.id} track={t} onPlay={handlePlay} />
            ))}
          </div>
        </div>
      )}

      {sections && sections.length === 0 && !fallbackTracks && (
        <div className="home-empty">
          <div className="home-empty__icon" aria-hidden>
            <Icon name="music" size={28} />
          </div>
          <div className="home-empty__title">
            Время первого трека
          </div>
          <div className="home-empty__hint">
            Запустите случайный поток — мы быстро подберём подборки
            под вас.
          </div>
          <div className="home-empty__actions">
            <button
              type="button"
              className="btn-primary home-empty__cta"
              onClick={handleStartFirstSession}
            >
              <Icon name="play" size={16} />
              <span>Начать слушать</span>
            </button>
            <button
              type="button"
              className="btn-secondary home-empty__alt"
              onClick={() => navigate('/radio')}
            >
              <Icon name="radio" size={16} />
              <span>Открыть радио</span>
            </button>
            <button
              type="button"
              className="btn-secondary home-empty__alt"
              onClick={() => navigate('/search')}
            >
              <Icon name="search" size={16} />
              <span>Искать треки</span>
            </button>
          </div>
        </div>
      )}
    </section>
  )
}



