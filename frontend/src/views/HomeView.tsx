import {
  type KeyboardEvent,
  useCallback,
  useEffect,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { NotificationBell } from '@/components/Notifications/NotificationBell'
<<<<<<< HEAD
import { AmbientStage } from '@/components/ui/AmbientStage'
import { HorizontalSnap } from '@/components/ui/HorizontalSnap'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
=======
import { usePullToRefresh } from '@/hooks/usePullToRefresh'
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
import { api, getApiErrorMessage } from '@/lib/api'
import { getInternalUserId } from '@/lib/telegram'
import { useBrandLabel } from '@/lib/brand'
import { m, VARIANTS_FADE_UP } from '@/lib/motion'
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

function coverUrl(key: string | null): string | null {
  if (!key) return null
  return `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(key)}`
}

function chunk<T>(items: readonly T[], size: number): T[][] {
  const out: T[][] = []
  for (let i = 0; i < items.length; i += size) {
    out.push(items.slice(i, i + size))
  }
  return out
}

function SkeletonBlock({ className }: { className: string }) {
  return <div className={`skeleton ${className}`} />
}

interface HomeTrackTileProps {
  track: Track
  onPlay: (t: Track) => void
}

function HomeTrackTile({ track, onPlay }: HomeTrackTileProps) {
  const { t } = useTranslation()
  const src = coverUrl(track.cover_key)
  const fallbackTitle = t('redesign.home.untitled')
  return (
    <button
      type="button"
      className="rh-home-tile"
      onClick={() => onPlay(track)}
      title={[track.title, track.artist].filter(Boolean).join(' — ')}
    >
      <div className="rh-home-tile__cover">
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
          <div className="rh-home-tile__ph">
            <Icon name="music" size={28} />
          </div>
        )}
      </div>
      <div className="rh-home-tile__title">
        {track.title || fallbackTitle}
      </div>
      {track.artist && (
        <div className="rh-home-tile__artist">
          {track.artist}
        </div>
      )}
    </button>
  )
}

<<<<<<< HEAD
interface HomeGenreMixCardProps {
=======
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
  const carouselRef = useRef<HTMLDivElement>(null)
  if (!tracks || !tracks.length) return null
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
          {tracks.filter(Boolean).map((t) => (
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
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
  mix: GenreMixItem
  onPlay: (tracks: Track[]) => void
  onOpen: () => void
  countLabel: string
  listenAria: string
}

<<<<<<< HEAD
function HomeGenreMixCard({
  mix,
  onPlay,
  onOpen,
  countLabel,
  listenAria,
}: HomeGenreMixCardProps) {
  const covers = mix.tracks
=======
function GenreMixCard({ mix, onPlay, onOpen }: GenreCardProps) {
  const tracks = mix.tracks || []
  const covers = tracks
    .filter(Boolean)
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
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
      className="rh-home-genre-card"
      onClick={onOpen}
      onKeyDown={handleCardKeyDown}
      title={mix.title}
    >
      <div className="rh-home-genre-card__mosaic">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="rh-home-genre-card__cell"
          >
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
      <div className="rh-home-genre-card__overlay" />
      <button
        type="button"
        className="rh-home-genre-card__play"
        onClick={(e) => {
          e.stopPropagation()
          if (tracks.length) onPlay(tracks)
        }}
        aria-label={listenAria}
      >
        <Icon name="play" size={14} />
      </button>
<<<<<<< HEAD
      <span className="rh-home-genre-card__genre">
        {mix.genre.charAt(0).toUpperCase() + mix.genre.slice(1)}
      </span>
      <span className="rh-home-genre-card__count">
        {countLabel}
=======
      <span className="home-genre-mix-card__genre">
        {(mix.genre || '').charAt(0).toUpperCase() + (mix.genre || '').slice(1)}
      </span>
      <span className="home-genre-mix-card__count">
        {tracks.length} треков
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
      </span>
    </div>
  )
}

interface HomeTrackSnapSectionProps {
  title: string
  tracks: Track[]
  onPlay: (t: Track) => void
  onMore?: () => void
  moreLabel: string
  snapAria: string
}

function HomeTrackSnapSection({
  title,
  tracks,
  onPlay,
  onMore,
  moreLabel,
  snapAria,
}: HomeTrackSnapSectionProps) {
  if (!tracks.length) return null
  const pages = chunk(tracks, 3)
  return (
    <>
      <div className="rh-home-section-head">
        <span className="rh-home-section-head__title">
          {title}
        </span>
        {onMore && (
          <button
            type="button"
            className="rh-home-section-head__link"
            onClick={onMore}
          >
            {moreLabel}
          </button>
        )}
      </div>
      <HorizontalSnap
        items={pages}
        renderItem={(page) => (
          <div className="rh-home-snap-page">
            {page.map((tr) => (
              <HomeTrackTile
                key={tr.id}
                track={tr}
                onPlay={onPlay}
              />
            ))}
          </div>
        )}
        pageDots
        parallax
        showArrows="never"
        className="rh-home-h-snap"
        ariaLabel={snapAria}
      />
    </>
  )
}

const QUICK_NAV: {
  morph?: string
  useCalendarIcon?: true
  labelKey: string
  path: string
}[] = [
  { useCalendarIcon: true, labelKey: 'quickDaily', path: '/daily-mix' },
  { morph: 'star', labelKey: 'quickWeekly', path: '/weekly-mix' },
  { morph: 'flame', labelKey: 'quickTop', path: '/weekly-top' },
  { morph: 'heart', labelKey: 'quickUserChoice', path: '/user-choice' },
  { morph: 'library', labelKey: 'quickLiked', path: '/library?tab=liked' },
  { morph: 'radio', labelKey: 'quickRadio', path: '/radio' },
]

interface HomeSectionConfig {
  key: string
  morePath?: string
}

/** Секции, которые рендерятся одинаковым HomeTrackSnapSection ниже hero/recent. */
const HOME_TRACK_SECTIONS: HomeSectionConfig[] = [
  { key: 'personalized' },
  { key: 'new_releases', morePath: '/search' },
  { key: 'genre_popular' },
  { key: 'user_choice', morePath: '/user-choice' },
  { key: 'fav_artists' },
  { key: 'popular' },
]

interface HomeViewProps {
  onOpenArtist?: (id: number) => void
}

export function HomeView({ onOpenArtist }: HomeViewProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
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
        showIsland({
          kind: 'error',
          title: getApiErrorMessage(e, t('redesign.home.playError')),
          durationMs: 4000,
        })
      }
    },
    [playTrack, t],
  )

  const handlePlayAll = useCallback(
    async (tracks: Track[]) => {
      if (!tracks.length) return
      try {
        await playTrack(tracks[0])
        trackActivationEvent('home_play_all')
      } catch (e) {
        showIsland({
          kind: 'error',
          title: getApiErrorMessage(e, t('redesign.home.playError')),
          durationMs: 4000,
        })
      }
    },
    [playTrack, t],
  )

  const handleStartRadio = useCallback(
    async (track: Track) => {
      try {
        await startRadio(track)
        trackActivationEvent('home_start_radio')
      } catch (e) {
        showIsland({
          kind: 'error',
          title: getApiErrorMessage(e, t('redesign.home.radioError')),
          durationMs: 4000,
        })
      }
    },
    [startRadio, t],
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
        showIsland({
          kind: 'error',
          title: t('redesign.home.emptyNoTracks'),
          durationMs: 3500,
        })
        return
      }
    }
    if (!candidates.length) {
      showIsland({
        kind: 'toast',
        title: t('redesign.home.emptyNoTracks'),
        durationMs: 3500,
      })
      return
    }
    try {
      await startRadio(candidates[0])
      trackActivationEvent('home_first_session_start')
    } catch (e) {
      showIsland({
        kind: 'error',
        title: getApiErrorMessage(e, t('redesign.home.startError')),
        durationMs: 4000,
      })
    }
  }, [sections, fallbackTracks, genreMixes, startRadio, t])

  const hour = new Date().getHours()
  const greeting =
    hour < 18
      ? t('redesign.home.greetingMorning')
      : t('redesign.home.greetingEvening')
  const displayName =
    me?.display_name ||
    me?.first_name ||
    me?.username ||
    null

  const sectionMap = new Map<string, HomeSection>()
  if (sections) {
    for (const s of sections) {
      if (s && s.section_type) {
        sectionMap.set(s.section_type, s)
      }
    }
  }
  const featuredSource =
    sectionMap.get('continue') ||
    sectionMap.get('personalized') ||
    sectionMap.get('user_choice') ||
    sectionMap.get('popular')
  const featuredTrack =
    featuredSource?.tracks?.[0] ||
    fallbackTracks?.[0] ||
    null
  const featuredEyebrow =
    featuredSource &&
    (featuredSource.section_type === 'continue' ||
      featuredSource.section_type === 'user_choice')
      ? featuredSource.title
      : brandLabel
  const loadingFeatured =
    sections === null && fallbackTracks === null
  const heroCoverSrc = featuredTrack
    ? coverUrl(featuredTrack.cover_key)
    : null

  const genreTrackCount = (n: number) =>
    t('artist.catalog_release_card_tracks_other', {
      count: n,
    })

  return (
    <section
      id="view-home"
      className="view active rh-home-root"
    >
      {(pull.pulling || pull.refreshing) && (
        <div
          className="rh-home-ptr"
          aria-live="polite"
          style={{
            height: pull.refreshing
              ? 36
              : Math.min(72, Math.round(pull.distance)),
            opacity: pull.refreshing
              ? 1
              : Math.min(1, pull.distance / 70),
            transition: pull.refreshing
              ? 'height .15s ease'
              : 'none',
          }}
        >
          {pull.refreshing
            ? t('redesign.home.ptrRefresh')
            : t('redesign.home.ptrPull')}
        </div>
      )}

      <m.div
        initial="hidden"
        animate="visible"
        variants={VARIANTS_FADE_UP}
      >
        <div className="rh-home-greeting">
          <div>
            <div className="rh-home-greeting__label">
              {displayName
                ? `${greeting} | ${displayName}`
                : greeting}
            </div>
            <div className="rh-home-greeting__sub">
              {brandLabel}
            </div>
          </div>
          <NotificationBell />
        </div>

        {featuredTrack ? (
          <div className="rh-home-hero">
            <AmbientStage
              coverUrl={heroCoverSrc ?? undefined}
            >
              <div className="rh-home-hero__inner">
                <div className="rh-home-hero__copy">
                  <span className="rh-home-hero__eyebrow">
                    {featuredEyebrow}
                  </span>
                  <h1 className="rh-home-hero__title">
                    {featuredTrack.title || t('redesign.home.untitled')}
                  </h1>
                  <p className="rh-home-hero__artist">
                    {featuredTrack.artist || brandLabel}
                  </p>
                  <div className="rh-home-hero__actions">
                    <MotionPress
                      variant="primary"
                      onClick={() => {
                        void handlePlay(featuredTrack)
                      }}
                    >
                      <Icon name="play" size={18} />
                      <span>{t('redesign.home.heroPlay')}</span>
                    </MotionPress>
                    <MotionPress
                      variant="ghost"
                      onClick={() => {
                        void handleStartRadio(featuredTrack)
                      }}
                    >
                      <Icon name="radio" size={18} />
                      <span>{t('redesign.home.heroRadio')}</span>
                    </MotionPress>
                  </div>
                </div>
                <div className="rh-home-hero__cover">
                  {heroCoverSrc ? (
                    <KenBurnsCover src={heroCoverSrc} alt="" />
                  ) : (
                    <div className="rh-home-tile__ph">
                      <Icon name="music" size={36} />
                    </div>
                  )}
                </div>
              </div>
            </AmbientStage>
          </div>
        ) : loadingFeatured ? (
          <div className="rh-home-hero--skeleton">
            <SkeletonBlock className="home-featured__skeleton-copy" />
            <SkeletonBlock className="home-featured__skeleton-cover" />
          </div>
        ) : null}

        <div className="rh-home-quick">
          {QUICK_NAV.map((item) => (
            <MotionPress
              key={item.path}
              variant="subtle"
              className="rh-home-quick-card glass--medium"
              onClick={() => navigate(item.path)}
            >
              <span
                className="rh-home-quick-card__icon"
                aria-hidden
              >
                {item.useCalendarIcon ? (
                  <Icon name="calendar" size={22} />
                ) : item.morph ? (
                  <MorphIcon
                    name={item.morph}
                    filled
                    size={22}
                  />
                ) : null}
              </span>
              <span className="rh-home-quick-card__label">
                {t(`redesign.home.${item.labelKey}`)}
              </span>
            </MotionPress>
          ))}
        </div>

        {genreMixes === null ? (
          <div>
            <div className="rh-home-section-head">
              <span className="rh-home-section-head__title">
                {t('redesign.home.sectionGenreMixes')}
              </span>
            </div>
            <div className="rh-home-skel-row home-skeleton-row">
              {[1, 2, 3].map((i) => (
                <SkeletonBlock
                  key={i}
                  className="home-skeleton-mix"
                />
              ))}
            </div>
          </div>
<<<<<<< HEAD
        ) : genreMixes.length > 0 ? (
          <>
            <div className="rh-home-section-head">
              <span className="rh-home-section-head__title">
                {t('redesign.home.sectionGenreMixes')}
              </span>
=======
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
          (sectionMap.get('continue')?.tracks ?? [])
            .filter(Boolean)
            .map((t) => t.id),
        )
        const recent = recentlyPlayed
          .filter(Boolean)
          .filter((t) => !continueIds.has(t.id))
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
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
            </div>
            <HorizontalSnap
              items={genreMixes}
              renderItem={(mix) => (
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'center',
                    width: '100%',
                  }}
                >
                  <HomeGenreMixCard
                    mix={mix}
                    onPlay={handlePlayAll}
                    onOpen={() =>
                      navigate(
                        `/genre-mix/${encodeURIComponent(mix.genre)}`,
                      )
                    }
                    countLabel={genreTrackCount(mix.tracks.length)}
                    listenAria={t('redesign.home.mixPlayAll')}
                  />
                </div>
              )}
              pageDots
              parallax
              showArrows="never"
              className="rh-home-h-snap"
              ariaLabel={t('redesign.home.sectionGenreMixes')}
            />
          </>
        ) : null}

        {sections === null ? (
          <div>
            <div className="rh-home-section-head">
              <span className="rh-home-section-head__title">
                {t('redesign.home.sectionContinue')}
              </span>
            </div>
            <div className="rh-home-skel-row home-skeleton-row">
              {[1, 2, 3, 4].map((i) => (
                <SkeletonBlock
                  key={i}
                  className="home-skeleton-tile"
                />
              ))}
            </div>
          </div>
        ) : (
          sectionMap.get('continue') && (
            <HomeTrackSnapSection
              title={sectionMap.get('continue')!.title}
              tracks={sectionMap.get('continue')!.tracks}
              onPlay={handlePlay}
              moreLabel={t('redesign.home.more')}
              snapAria={sectionMap.get('continue')!.title}
            />
          )
        )}

        {recentlyPlayed === null ? (
          <div>
            <div className="rh-home-section-head">
              <span className="rh-home-section-head__title">
                {t('redesign.home.sectionRecent')}
              </span>
            </div>
            <div className="rh-home-skel-row home-skeleton-row">
              {[1, 2, 3, 4].map((i) => (
                <SkeletonBlock
                  key={i}
                  className="home-skeleton-tile"
                />
              ))}
            </div>
          </div>
        ) : (() => {
          const continueIds = new Set(
            (sectionMap.get('continue')?.tracks ?? []).map(
              (tr) => tr.id,
            ),
          )
          const recent = recentlyPlayed.filter(
            (tr) => !continueIds.has(tr.id),
          )
          if (recent.length === 0) return null
          return (
            <HomeTrackSnapSection
              title={t('redesign.home.sectionRecent')}
              tracks={recent}
              onPlay={handlePlay}
              moreLabel={t('redesign.home.more')}
              snapAria={t('redesign.home.sectionRecent')}
            />
          )
        })()}

        {followedArtists === null ? (
          <div>
            <div className="rh-home-section-head">
              <span className="rh-home-section-head__title">
                {t('redesign.home.sectionSubscriptions')}
              </span>
            </div>
            <div className="rh-home-skel-row">
              {[1, 2, 3, 4, 5].map((i) => (
                <SkeletonBlock
                  key={i}
                  className="home-skeleton-chip"
                />
              ))}
            </div>
          </div>
        ) : followedArtists.length > 0 ? (
          <>
            <div className="rh-home-section-head">
              <span className="rh-home-section-head__title">
                {t('redesign.home.sectionSubscriptions')}
              </span>
            </div>
            <HorizontalSnap
              items={chunk(followedArtists, 4)}
              renderItem={(page) => (
                <div className="rh-home-artist-page">
                  {page.map((artist) => {
                    const src = coverUrl(artist.image_key)
                    return (
                      <button
                        key={artist.id}
                        type="button"
                        className="rh-home-artist-chip"
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
                        <div className="rh-home-artist-chip__avatar">
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
                            <div className="rh-home-artist-chip__ph">
                              <Icon name="user" size={24} />
                            </div>
                          )}
                        </div>
                        <span className="rh-home-artist-chip__name">
                          {artist.name}
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}
              pageDots
              parallax
              showArrows="never"
              className="rh-home-h-snap rh-home-artist-snap"
              ariaLabel={t('redesign.home.sectionSubscriptions')}
            />
          </>
        ) : null}

        {sections &&
          HOME_TRACK_SECTIONS.map(({ key, morePath }) => {
            const s = sectionMap.get(key)
            if (!s) return null
            return (
              <HomeTrackSnapSection
                key={key}
                title={s.title}
                tracks={s.tracks}
                onPlay={handlePlay}
                onMore={
                  morePath ? () => navigate(morePath) : undefined
                }
                moreLabel={t('redesign.home.more')}
                snapAria={s.title}
              />
            )
          })}

        {!sections && fallbackTracks !== null && fallbackTracks.length > 0 && (
          <HomeTrackSnapSection
            title={t('redesign.home.sectionTracks')}
            tracks={fallbackTracks}
            onPlay={handlePlay}
            moreLabel={t('redesign.home.more')}
            snapAria={t('redesign.home.sectionTracks')}
          />
        )}

        {sections && sections.length === 0 && !fallbackTracks && (
          <div className="rh-home-empty">
            <div className="rh-home-empty__icon" aria-hidden>
              <Icon name="music" size={28} />
            </div>
            <div className="rh-home-empty__title">
              {t('redesign.home.emptyTitle')}
            </div>
            <div className="rh-home-empty__hint">
              {t('redesign.home.emptyHint')}
            </div>
            <div className="rh-home-empty__actions">
              <MotionPress
                variant="primary"
                className="rh-home-empty__cta"
                onClick={() => {
                  void handleStartFirstSession()
                }}
              >
                <Icon name="play" size={16} />
                <span>{t('redesign.home.emptyStart')}</span>
              </MotionPress>
              <MotionPress
                variant="ghost"
                className="rh-home-empty__alt"
                onClick={() => navigate('/radio')}
              >
                <Icon name="radio" size={16} />
                <span>{t('redesign.home.emptyRadio')}</span>
              </MotionPress>
              <MotionPress
                variant="ghost"
                className="rh-home-empty__alt"
                onClick={() => navigate('/search')}
              >
                <Icon name="search" size={16} />
                <span>{t('redesign.home.emptySearch')}</span>
              </MotionPress>
            </div>
          </div>
        )}
      </m.div>
    </section>
  )
}
