import {
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { NotificationBell } from '@/components/Notifications/NotificationBell'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { HorizontalSnap } from '@/components/ui/HorizontalSnap'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
import { api, getApiErrorMessage } from '@/lib/api'
import { getInternalUserId } from '@/lib/telegram'
import { useBrandLabel } from '@/lib/brand'
import { m, VARIANTS_FADE_UP } from '@/lib/motion'
import { usePlayerActions } from '@/store/PlayerContext'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import { trackActivationEvent } from '@/lib/activation'
import { usePullToRefresh } from '@/hooks/usePullToRefresh'
import { PullToRefreshIndicator } from '@/components/ui/PullToRefreshIndicator'
import { useDesktopFinePointer } from '@/hooks/useDesktopFinePointer'
import { useNavigateToArtistByName } from '@/hooks/useNavigateToArtistByName'
import {
  HOME_QUICK_VISIBLE_COUNT,
  MIX_SHORTCUT_TILES,
} from '@/lib/homeShortcuts'
import {
  coverProxySrcSet,
  coverProxyUrl,
  type CoverRenderWidth,
} from '@/lib/coverProxy'
import '@/styles/redesign-home.css'
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

function coverUrl(
  key: string | null,
  width: CoverRenderWidth = 240,
): string | null {
  if (!key) return null
  return coverProxyUrl(key, { width })
}

function chunk<T>(items: readonly T[], size: number): T[][] {
  const out: T[][] = []
  for (let i = 0; i < items.length; i += size) {
    out.push(items.slice(i, i + size))
  }
  return out
}

const HOME_DATA_WATCHDOG_MS = 22_000

const HOME_RADIO_SECTION_ORDER = [
  'continue',
  'personalized',
  'user_choice',
  'new_releases',
  'genre_popular',
  'fav_artists',
  'popular',
] as const

function pickHomeRadioSeedFromSections(
  sections: HomeSection[] | null,
): Track | null {
  if (!sections?.length) return null
  for (const key of HOME_RADIO_SECTION_ORDER) {
    const section = sections.find((s) => s.section_type === key)
    const first = section?.tracks?.[0]
    if (first) return first
  }
  return null
}

async function resolveHomeRadioSeedTrack(
  sections: HomeSection[] | null,
  genreMixes: GenreMixItem[] | null,
  fallbackTracks: Track[] | null,
): Promise<Track | null> {
  const fromSections = pickHomeRadioSeedFromSections(sections)
  if (fromSections) return fromSections
  if (genreMixes?.length && genreMixes[0].tracks?.length) {
    return genreMixes[0].tracks[0]
  }
  if (fallbackTracks?.length) return fallbackTracks[0]
  try {
    const data = await api.getTracks({ size: 30 })
    return data.items[0] ?? null
  } catch {
    return null
  }
}

function normalizeHomeSections(
  raw: HomeSection[] | null | undefined,
): HomeSection[] {
  if (!Array.isArray(raw)) return []
  return raw
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
  const desktopFineNav = useDesktopFinePointer()
  const goArtistByName = useNavigateToArtistByName()
  const src = coverUrl(track.cover_key)
  const [coverFailed, setCoverFailed] = useState(false)
  const fallbackTitle = t('redesign.home.untitled')
  const titleAttr = [track.title, track.artist]
    .filter(Boolean)
    .join(' — ')
  const coverBlock = (
    <div className="rh-home-tile__cover">
      {src && !coverFailed ? (
        <img
          src={src}
          alt=""
          width={112}
          height={112}
          loading="lazy"
          decoding="async"
          onError={() => setCoverFailed(true)}
        />
      ) : (
        <div className="rh-home-tile__ph">
          <Icon name="music" size={28} />
        </div>
      )}
    </div>
  )
  if (desktopFineNav && track.artist) {
    return (
      <div className="rh-home-tile rh-home-tile--split-desktop">
        <button
          type="button"
          className="rh-home-tile__playback"
          onClick={() => onPlay(track)}
          title={titleAttr}
        >
          {coverBlock}
          <div className="rh-home-tile__title">
            {track.title || fallbackTitle}
          </div>
        </button>
        <button
          type="button"
          className="rh-home-tile__artist-link"
          onClick={() => void goArtistByName(track.artist)}
          title={track.artist}
        >
          {track.artist}
        </button>
      </div>
    )
  }
  return (
    <button
      type="button"
      className="rh-home-tile"
      onClick={() => onPlay(track)}
      title={titleAttr}
    >
      {coverBlock}
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

interface HomeGenreMixCardProps {
  mix: GenreMixItem
  onPlay: (tracks: Track[]) => void
  onOpen: () => void
  countLabel: string
  listenAria: string
}

function HomeGenreCell({ src }: { src: string | null }) {
  const [failed, setFailed] = useState(false)
  return (
    <div className="rh-home-genre-card__cell">
      {src && !failed ? (
        <img
          src={src}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
        />
      ) : (
        <Icon name="music" size={14} />
      )}
    </div>
  )
}

function HomeGenreMixCard({
  mix,
  onPlay,
  onOpen,
  countLabel,
  listenAria,
}: HomeGenreMixCardProps) {
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
      className="rh-home-genre-card"
      onClick={onOpen}
      onKeyDown={handleCardKeyDown}
      title={mix.title}
    >
      <div className="rh-home-genre-card__mosaic">
        {Array.from({ length: 4 }).map((_, i) => (
          <HomeGenreCell key={i} src={covers[i] ?? null} />
        ))}
      </div>
      <div className="rh-home-genre-card__overlay" />
      <button
        type="button"
        className="rh-home-genre-card__play"
        onClick={(e) => {
          e.stopPropagation()
          if (mix.tracks.length) onPlay(mix.tracks)
        }}
        aria-label={listenAria}
      >
        <Icon name="play" size={14} />
      </button>
      <span className="rh-home-genre-card__genre">
        {mix.genre.charAt(0).toUpperCase() + mix.genre.slice(1)}
      </span>
      <span className="rh-home-genre-card__count">
        {countLabel}
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

function HomeArtistAvatar({ src }: { src: string | null }) {
  const [failed, setFailed] = useState(false)
  if (src && !failed) {
    return (
      <img
        src={src}
        alt=""
        width={64}
        height={64}
        loading="lazy"
        decoding="async"
        onError={() => setFailed(true)}
      />
    )
  }
  return (
    <div className="rh-home-artist-chip__ph">
      <Icon name="user" size={24} />
    </div>
  )
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
        parallax={false}
        showArrows="never"
        className="rh-home-h-snap"
        ariaLabel={snapAria}
      />
    </>
  )
}

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
  const desktopFineNav = useDesktopFinePointer()
  const goArtistByName = useNavigateToArtistByName()

  const [me, setMe] = useState<UserResponse | null>(null)
  const [sections, setSections] = useState<HomeSection[] | null>(null)
  const [genreMixes, setGenreMixes] = useState<GenreMixItem[] | null>(null)
  const [followedArtists, setFollowedArtists] = useState<
    FollowedArtistItem[] | null
  >(null)
  const [recentlyPlayed, setRecentlyPlayed] = useState<Track[] | null>(null)
  const [fallbackTracks, setFallbackTracks] = useState<Track[] | null>(null)
  const [highlight, setHighlight] = useState<{
    kind: string
    reason_code: string
    track_id: number
    title: string
    artist: string | null
    cover_key: string | null
    access_mode: string
    catalog_type: string
  } | null>(null)
  const [headerStuck, setHeaderStuck] = useState(false)
  const sentinelRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false
    const watchdogId = window.setTimeout(() => {
      if (cancelled) return
      setSections((s) => (s === null ? [] : s))
      setGenreMixes((g) => (g === null ? [] : g))
      setFollowedArtists((f) => (f === null ? [] : f))
      setRecentlyPlayed((r) => (r === null ? [] : r))
      void api
        .getTracks({ size: 50 })
        .then((data) => {
          if (cancelled) return
          setFallbackTracks((fb) =>
            fb === null ? data.items : fb,
          )
        })
        .catch(() => {
          if (cancelled) return
          setFallbackTracks((fb) => (fb === null ? [] : fb))
        })
    }, HOME_DATA_WATCHDOG_MS)

    const uid = getInternalUserId()
    if (uid) {
      api.getUserProfile(uid).then(setMe).catch(() => {})
    }

    api
      .getHomeRecommendations()
      .then((data) => {
        if (cancelled) return
        setSections(normalizeHomeSections(data.sections))
      })
      .catch(() => {
        if (cancelled) return
        api
          .getTracks({ size: 50 })
          .then((data) => setFallbackTracks(data.items))
          .catch(() => setFallbackTracks([]))
      })

    api
      .getHomeHighlight()
      .then((res) => {
        if (cancelled) return
        setHighlight(res ?? null)
      })
      .catch(() => {
        if (cancelled) return
        setHighlight(null)
      })

    api
      .getGenreMixes()
      .then((data) => {
        if (cancelled) return
        setGenreMixes(data.mixes)
      })
      .catch(() => {
        if (cancelled) return
        setGenreMixes([])
      })

    api
      .getFollowedArtistsList(30)
      .then((data) => {
        if (cancelled) return
        setFollowedArtists(data.items)
      })
      .catch(() => {
        if (cancelled) return
        setFollowedArtists([])
      })

    api
      .getListenHistory(20)
      .then((data) => {
        if (cancelled) return
        setRecentlyPlayed(data.items)
      })
      .catch(() => {
        if (cancelled) return
        setRecentlyPlayed([])
      })

    return () => {
      cancelled = true
      window.clearTimeout(watchdogId)
    }
  }, [])

  const handleRefresh = useCallback(async () => {
    setSections(null)
    setGenreMixes(null)
    setFollowedArtists(null)
    setRecentlyPlayed(null)
    await Promise.allSettled([
      api
        .getHomeRecommendations()
        .then((data) =>
          setSections(normalizeHomeSections(data.sections)),
        )
        .catch(() => {
          setSections([])
          return api
            .getTracks({ size: 50 })
            .then((data) => setFallbackTracks(data.items))
            .catch(() => setFallbackTracks([]))
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
    const sentinel = sentinelRef.current
    const main = document.getElementById('main')
    if (!sentinel || !main) return
    const io = new IntersectionObserver(
      ([entry]) => setHeaderStuck(!entry.isIntersecting),
      { root: main, threshold: 0, rootMargin: '0px 0px 0px 0px' },
    )
    io.observe(sentinel)
    return () => io.disconnect()
  }, [])

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

  const handleStartRadioFromHomeRecommendations = useCallback(
    async (
      activation: 'home_start_radio' | 'home_first_session_start',
    ) => {
      const seed = await resolveHomeRadioSeedTrack(
        sections,
        genreMixes,
        fallbackTracks,
      )
      navigate('/radio')
      if (!seed) {
        showIsland({
          kind: 'toast',
          title: t('redesign.home.emptyNoTracks'),
          durationMs: 3500,
        })
        return
      }
      try {
        await startRadio(seed)
        trackActivationEvent(activation)
      } catch (e) {
        showIsland({
          kind: 'error',
          title: getApiErrorMessage(
            e,
            activation === 'home_start_radio'
              ? t('redesign.home.radioError')
              : t('redesign.home.startError'),
          ),
          durationMs: 4000,
        })
      }
    },
    [
      sections,
      fallbackTracks,
      genreMixes,
      navigate,
      startRadio,
      t,
    ],
  )

  const handleStartFirstSession = useCallback(async () => {
    await handleStartRadioFromHomeRecommendations(
      'home_first_session_start',
    )
  }, [handleStartRadioFromHomeRecommendations])

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
  const highlightTrack: Track | null = highlight
    ? ({
        id: highlight.track_id,
        title: highlight.title,
        artist: highlight.artist,
        cover_key: highlight.cover_key,
        access_mode: highlight.access_mode,
        catalog_type: highlight.catalog_type,
      } as unknown as Track)
    : null
  const recentHeroTrack =
    recentlyPlayed !== null && recentlyPlayed.length > 0
      ? recentlyPlayed[0]
      : null
  const featuredTrack =
    recentHeroTrack ||
    highlightTrack ||
    featuredSource?.tracks?.[0] ||
    fallbackTracks?.[0] ||
    null
  const heroFromRecentListen =
    recentHeroTrack !== null &&
    featuredTrack !== null &&
    featuredTrack.id === recentHeroTrack.id
  const highlightEyebrow = highlight
    ? t(
        `redesign.home.highlight.${highlight.reason_code}`,
        highlight.reason_code,
      )
    : null
  const featuredEyebrow = heroFromRecentListen
    ? t('redesign.home.sectionRecent')
    : highlightEyebrow ||
      (featuredSource &&
      (featuredSource.section_type === 'continue' ||
        featuredSource.section_type === 'user_choice')
        ? featuredSource.title
        : brandLabel)
  const loadingFeatured =
    sections === null &&
    fallbackTracks === null &&
    recentlyPlayed === null
  const heroCoverSrc = featuredTrack
    ? coverUrl(featuredTrack.cover_key, 480)
    : null
  const heroCoverSrcSet = featuredTrack?.cover_key
    ? coverProxySrcSet(featuredTrack.cover_key)
    : undefined

  const genreTrackCount = (n: number) =>
    t('artist.catalog_release_card_tracks_other', {
      count: n,
    })

  return (
    <section
      id="view-home"
      className="view active rh-home-root"
    >
      <PullToRefreshIndicator state={pull} />
      <span className="sr-only" aria-live="polite">
        {pull.refreshing
          ? t('redesign.home.ptrRefresh')
          : pull.pulling
            ? t('redesign.home.ptrPull')
            : ''}
      </span>

      <div ref={sentinelRef} aria-hidden style={{ height: 0 }} />
      <header
        className={
          headerStuck
            ? 'rh-home-header is-stuck'
            : 'rh-home-header'
        }
      >
        <div className="rh-home-greeting">
          <div className="rh-home-greeting__copy">
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
      </header>

      <m.div
        initial="hidden"
        animate="visible"
        variants={VARIANTS_FADE_UP}
      >

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
                  <p
                    className={
                      desktopFineNav &&
                      featuredTrack.artist
                        ? 'rh-home-hero__artist rh-home-hero__artist--nav'
                        : 'rh-home-hero__artist'
                    }
                    role={
                      desktopFineNav &&
                      featuredTrack.artist
                        ? 'link'
                        : undefined
                    }
                    tabIndex={
                      desktopFineNav &&
                      featuredTrack.artist
                        ? 0
                        : undefined
                    }
                    onClick={
                      desktopFineNav &&
                      featuredTrack.artist
                        ? () => {
                            void goArtistByName(
                              featuredTrack.artist,
                            )
                          }
                        : undefined
                    }
                    onKeyDown={
                      desktopFineNav &&
                      featuredTrack.artist
                        ? (e) => {
                            if (
                              e.key === 'Enter' ||
                              e.key === ' '
                            ) {
                              e.preventDefault()
                              void goArtistByName(
                                featuredTrack.artist,
                              )
                            }
                          }
                        : undefined
                    }
                  >
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
                        void handleStartRadioFromHomeRecommendations(
                          'home_start_radio',
                        )
                      }}
                    >
                      <Icon name="radio" size={18} />
                      <span>{t('redesign.home.heroRadio')}</span>
                    </MotionPress>
                  </div>
                </div>
                <div className="rh-home-hero__cover">
                  {heroCoverSrc ? (
                    <KenBurnsCover
                      src={heroCoverSrc}
                      srcSet={heroCoverSrcSet}
                      alt=""
                    />
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

        <div className="rh-home-quick rh-home-quick--few-tiles">
          {MIX_SHORTCUT_TILES.slice(
            0,
            HOME_QUICK_VISIBLE_COUNT,
          ).map((item) => (
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
                {'morph' in item ? (
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
        ) : genreMixes.length > 0 ? (
          <>
            <div className="rh-home-section-head">
              <span className="rh-home-section-head__title">
                {t('redesign.home.sectionGenreMixes')}
              </span>
            </div>
            <HorizontalSnap
              items={genreMixes}
              renderItem={(mix) => (
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
              )}
              pageDots
              parallax={false}
              showArrows="never"
              className="rh-home-h-snap rh-home-genre-snap"
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
                          <HomeArtistAvatar src={src} />
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
              parallax={false}
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
