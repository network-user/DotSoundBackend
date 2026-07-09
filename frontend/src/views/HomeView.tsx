import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { HomeQuickShortcuts } from '@/components/home/HomeQuickShortcuts'
import { NotificationBell } from '@/components/Notifications/NotificationBell'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
import { api, getApiErrorMessage } from '@/lib/api'
import { getInternalUserId } from '@/lib/telegram'
import { useBrandLabel } from '@/lib/brand'
import { m, VARIANTS_FADE_UP } from '@/lib/motion'
import { usePlayerActions } from '@/store/PlayerContext'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import { trackActivationEvent } from '@/lib/activation'
import { useAutoLoadMore } from '@/hooks/useAutoLoadMore'
import { useMainScrollRestore } from '@/hooks/useMainScrollRestore'
import { usePullToRefresh } from '@/hooks/usePullToRefresh'
import { PullToRefreshIndicator } from '@/components/ui/PullToRefreshIndicator'
import { useDesktopFinePointer } from '@/hooks/useDesktopFinePointer'
import { useNavigateToArtistByName } from '@/hooks/useNavigateToArtistByName'
import {
  coverProxySrcSet,
  coverProxyUrl,
  type CoverRenderWidth,
} from '@/lib/coverProxy'
import '@/styles/dot-home.css'
import type {
  FollowedArtistItem,
  GenreMixItem,
  PromotionPublic,
  Track,
  UserResponse,
} from '@/types/api'
import { PromotionHero } from '@/components/Promotion/PromotionHero'
import { PromotionSection } from '@/components/Promotion/PromotionSection'

interface HomeSection {
  title: string
  section_type: string
  tracks: Track[]
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

const HOME_LAZY_SECTIONS: ReadonlyArray<{
  key: string
  morePath?: string
}> = [
  { key: 'personalized' },
  { key: 'new_releases', morePath: '/search' },
  { key: 'genre_popular' },
  { key: 'user_choice', morePath: '/user-choice' },
  { key: 'fav_artists' },
  { key: 'popular' },
]

function coverUrl(
  key: string | null,
  width: CoverRenderWidth = 240,
): string | null {
  if (!key) return null
  return coverProxyUrl(key, { width })
}

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

function resolveSectionTitle(
  section: HomeSection,
  t: (key: string, defaultValue: string) => string,
): string {
  return t(
    `redesign.home.sectionTitle.${section.section_type}`,
    section.title,
  )
}

interface DhTileProps {
  track: Track
  onPlay: (t: Track) => void
}

const DhTile = memo(function DhTile({ track, onPlay }: DhTileProps) {
  const { t } = useTranslation()
  const desktopFine = useDesktopFinePointer()
  const goArtistByName = useNavigateToArtistByName()
  const [coverFailed, setCoverFailed] = useState(false)
  const src = coverUrl(track.cover_key)
  const fallbackTitle = t('redesign.home.untitled')
  const titleAttr = [track.title, track.artist]
    .filter(Boolean)
    .join(' — ')
  const handleArtistClick = (e: React.MouseEvent) => {
    if (!desktopFine || !track.artist) return
    e.stopPropagation()
    void goArtistByName(track.artist)
  }
  return (
    <button
      type="button"
      className="dh-tile"
      onClick={() => onPlay(track)}
      title={titleAttr}
      aria-label={titleAttr || fallbackTitle}
    >
      <div className="dh-tile__cover">
        {src && !coverFailed ? (
          <img
            src={src}
            alt=""
            width={148}
            height={148}
            loading="lazy"
            decoding="async"
            onError={() => setCoverFailed(true)}
          />
        ) : (
          <div className="dh-tile__ph">
            <Icon name="music" size={24} />
          </div>
        )}
        <span className="dh-tile__overlay" aria-hidden>
          <span className="dh-tile__overlay-btn">
            <Icon name="play" size={16} />
          </span>
        </span>
      </div>
      <p className="dh-tile__title" dir="auto">
        {track.title || fallbackTitle}
      </p>
      {track.artist && (
        <p
          className={
            desktopFine
              ? 'dh-tile__artist dh-tile__artist--nav'
              : 'dh-tile__artist'
          }
          dir="auto"
          onClick={handleArtistClick}
        >
          {track.artist}
        </p>
      )}
    </button>
  )
})

interface DhSectionHeadProps {
  title: string
  onMore?: () => void
  moreLabel: string
}

function DhSectionHead({
  title,
  onMore,
  moreLabel,
}: DhSectionHeadProps) {
  return (
    <div className="dh-section-head">
      <h3 className="dh-section-head__title">{title}</h3>
      {onMore && (
        <button
          type="button"
          className="dh-section-head__more"
          onClick={onMore}
        >
          {moreLabel}
        </button>
      )}
    </div>
  )
}

interface DhTileRowProps {
  title: string
  tracks: Track[]
  onPlay: (t: Track) => void
  onMore?: () => void
  moreLabel: string
  ariaLabel: string
}

function DhTileRow({
  title,
  tracks,
  onPlay,
  onMore,
  moreLabel,
  ariaLabel,
}: DhTileRowProps) {
  if (!tracks.length) return null
  return (
    <section className="dh-section" aria-label={ariaLabel}>
      <DhSectionHead
        title={title}
        onMore={onMore}
        moreLabel={moreLabel}
      />
      <div className="dh-scroller" role="list">
        {tracks.map((tr) => (
          <div role="listitem" key={tr.id}>
            <DhTile track={tr} onPlay={onPlay} />
          </div>
        ))}
      </div>
    </section>
  )
}

function DhMixCell({ src }: { src: string | null }) {
  const [failed, setFailed] = useState(false)
  return (
    <div className="dh-mix__cell">
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

interface DhMixCardProps {
  mix: GenreMixItem
  countLabel: string
  onOpen: () => void
  onPlay: (tracks: Track[]) => void
  listenAria: string
}

const DhMixCard = memo(function DhMixCard({
  mix,
  countLabel,
  onOpen,
  onPlay,
  listenAria,
}: DhMixCardProps) {
  const covers = mix.tracks
    .slice(0, 4)
    .map((t) => coverUrl(t.cover_key))
  while (covers.length < 4) covers.push(null)
  return (
    <button
      type="button"
      className="dh-mix"
      onClick={onOpen}
      title={mix.title}
    >
      <div className="dh-mix__cover">
        <div className="dh-mix__mosaic">
          {covers.map((src, i) => (
            <DhMixCell key={i} src={src} />
          ))}
        </div>
        <span
          className="dh-mix__play"
          onClick={(e) => {
            e.stopPropagation()
            if (mix.tracks.length) onPlay(mix.tracks)
          }}
          role="button"
          tabIndex={-1}
          aria-label={listenAria}
        >
          <Icon name="play" size={14} />
        </span>
      </div>
      <p className="dh-mix__title">{mix.genre}</p>
      <p className="dh-mix__count">{countLabel}</p>
    </button>
  )
})

interface DhArtistChipProps {
  artist: FollowedArtistItem
  onOpen: (artist: FollowedArtistItem) => void
}

const DhArtistChip = memo(function DhArtistChip({
  artist,
  onOpen,
}: DhArtistChipProps) {
  const [failed, setFailed] = useState(false)
  const src = coverUrl(artist.image_key)
  return (
    <button
      type="button"
      className="dh-artist"
      onClick={() => onOpen(artist)}
      title={artist.name}
    >
      <div className="dh-artist__avatar">
        {src && !failed ? (
          <img
            src={src}
            alt=""
            width={64}
            height={64}
            loading="lazy"
            decoding="async"
            onError={() => setFailed(true)}
          />
        ) : (
          <div className="dh-artist__ph">
            <Icon name="user" size={28} />
          </div>
        )}
      </div>
      <span className="dh-artist__name">{artist.name}</span>
    </button>
  )
})

interface DhLazyTileRowProps {
  sectionKey: string
  initialSection: HomeSection | null
  fallbackTitle: string
  onLoaded: (section: HomeSection) => void
  onPlay: (track: Track) => void
  onMore?: () => void
  moreLabel: string
}

function DhLazyTileRow({
  sectionKey,
  initialSection,
  fallbackTitle,
  onLoaded,
  onPlay,
  onMore,
  moreLabel,
}: DhLazyTileRowProps) {
  const { t } = useTranslation()
  const [section, setSection] = useState<HomeSection | null>(
    initialSection,
  )
  const [loaded, setLoaded] = useState(Boolean(initialSection))
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!initialSection) return
    setSection(initialSection)
    setLoaded(true)
  }, [initialSection])

  const load = useCallback(async () => {
    if (loading || loaded) return
    setLoading(true)
    try {
      const next = await api.getHomeSection(sectionKey, 15)
      setSection(next)
      onLoaded(next)
    } catch {
      setSection({
        title: fallbackTitle,
        section_type: sectionKey,
        tracks: [],
      })
    } finally {
      setLoaded(true)
      setLoading(false)
    }
  }, [fallbackTitle, loaded, loading, onLoaded, sectionKey])

  const sentinelRef = useAutoLoadMore({
    enabled: !loaded,
    loading,
    onLoadMore: load,
    rootMargin: '900px',
  })

  if (loaded && (!section || section.tracks.length === 0)) {
    return null
  }

  if (!section || section.tracks.length === 0) {
    return (
      <section className="dh-section" ref={sentinelRef}>
        <DhSectionHead
          title={fallbackTitle}
          moreLabel={moreLabel}
        />
        <div className="dh-scroller" aria-hidden>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="dh-skel dh-skel--tile" />
          ))}
        </div>
      </section>
    )
  }

  const title = resolveSectionTitle(section, t)
  return (
    <DhTileRow
      title={title}
      tracks={section.tracks}
      onPlay={onPlay}
      onMore={onMore}
      moreLabel={moreLabel}
      ariaLabel={title}
    />
  )
}

interface HomeViewProps {
  onOpenArtist?: (id: number) => void
}

export function HomeView({ onOpenArtist }: HomeViewProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { playTrack, startRadio } = usePlayerActions()
  const brandLabel = useBrandLabel()
  const desktopFine = useDesktopFinePointer()
  const goArtistByName = useNavigateToArtistByName()

  const [me, setMe] = useState<UserResponse | null>(null)
  const [sections, setSections] = useState<HomeSection[] | null>(null)
  const [genreMixes, setGenreMixes] = useState<GenreMixItem[] | null>(
    null,
  )
  const [genreMixesLoading, setGenreMixesLoading] = useState(false)
  const [followedArtists, setFollowedArtists] = useState<
    FollowedArtistItem[] | null
  >(null)
  const [followedArtistsLoading, setFollowedArtistsLoading] =
    useState(false)
  const [recentlyPlayed, setRecentlyPlayed] = useState<
    Track[] | null
  >(null)
  const [fallbackTracks, setFallbackTracks] = useState<Track[] | null>(
    null,
  )
  const [promoHero, setPromoHero] = useState<PromotionPublic[] | null>(
    null,
  )
  const [promoSection, setPromoSection] = useState<
    PromotionPublic[] | null
  >(null)
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
    let active = true
    const loadPromotions = () => {
      void api
        .getHeroPromotions(3)
        .then((res) => {
          if (active) setPromoHero(res.items)
        })
        .catch(() => {
          if (active) setPromoHero([])
        })
      void api
        .getSectionPromotions(10)
        .then((res) => {
          if (active) setPromoSection(res.items)
        })
        .catch(() => {
          if (active) setPromoSection([])
        })
    }
    const idleId =
      typeof window.requestIdleCallback === 'function'
        ? window.requestIdleCallback(loadPromotions, {
            timeout: 1800,
          })
        : window.setTimeout(loadPromotions, 480)
    return () => {
      active = false
      if (typeof idleId === 'number') {
        window.clearTimeout(idleId)
      } else if (
        typeof window.cancelIdleCallback === 'function'
      ) {
        window.cancelIdleCallback(idleId)
      }
    }
  }, [])

  const handlePromotionSelect = useCallback(
    (item: PromotionPublic) => {
      switch (item.entity_type) {
        case 'artist':
          if (onOpenArtist) onOpenArtist(item.entity_id)
          else navigate(`/artist/${item.entity_id}`)
          break
        case 'track':
          navigate(`/track/${item.entity_id}`)
          break
        case 'playlist':
          navigate(`/playlist/${item.entity_id}`)
          break
        case 'album':
          navigate(`/album/${item.entity_id}`)
          break
      }
    },
    [navigate, onOpenArtist],
  )

  const upsertHomeSection = useCallback((section: HomeSection) => {
    setSections((prev) => {
      const current = prev ?? []
      const next = current.filter(
        (s) => s.section_type !== section.section_type,
      )
      return [...next, section]
    })
  }, [])

  const loadGenreMixes = useCallback(async () => {
    if (genreMixes !== null || genreMixesLoading) return
    setGenreMixesLoading(true)
    try {
      const data = await api.getGenreMixes()
      setGenreMixes(data.mixes)
    } catch {
      setGenreMixes([])
    } finally {
      setGenreMixesLoading(false)
    }
  }, [genreMixes, genreMixesLoading])

  const loadFollowedArtists = useCallback(async () => {
    if (followedArtists !== null || followedArtistsLoading) return
    setFollowedArtistsLoading(true)
    try {
      const data = await api.getFollowedArtistsList(16)
      setFollowedArtists(data.items)
    } catch {
      setFollowedArtists([])
    } finally {
      setFollowedArtistsLoading(false)
    }
  }, [followedArtists, followedArtistsLoading])

  const genreMixesSentinelRef = useAutoLoadMore({
    enabled: genreMixes === null,
    loading: genreMixesLoading,
    onLoadMore: loadGenreMixes,
    rootMargin: '900px',
  })
  const followedArtistsSentinelRef = useAutoLoadMore({
    enabled: followedArtists === null,
    loading: followedArtistsLoading,
    onLoadMore: loadFollowedArtists,
    rootMargin: '900px',
  })

  useEffect(() => {
    let cancelled = false
    const watchdogId = window.setTimeout(() => {
      if (cancelled) return
      setSections((s) => (s === null ? [] : s))
      setRecentlyPlayed((r) => (r === null ? [] : r))
      void api
        .getTracks({ size: 15 })
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
    const loadProfile = () => {
      if (!uid) return
      void api.getUserProfile(uid).then(setMe).catch(() => {})
    }
    const profileIdleId =
      typeof window.requestIdleCallback === 'function'
        ? window.requestIdleCallback(loadProfile, { timeout: 2400 })
        : window.setTimeout(loadProfile, 720)

    api
      .getHomeSection('continue', 10)
      .then((section) => {
        if (cancelled) return
        setSections(section.tracks.length ? [section] : [])
      })
      .catch(() => {
        if (cancelled) return
        setSections([])
        api
          .getTracks({ size: 15 })
          .then((data) => {
            if (cancelled) return
            setFallbackTracks(data.items)
          })
          .catch(() => {
            if (cancelled) return
            setFallbackTracks([])
          })
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
      if (typeof profileIdleId === 'number') {
        window.clearTimeout(profileIdleId)
      } else if (
        typeof window.cancelIdleCallback === 'function'
      ) {
        window.cancelIdleCallback(profileIdleId)
      }
    }
  }, [])

  const handleRefresh = useCallback(async () => {
    setSections(null)
    setGenreMixes(null)
    setGenreMixesLoading(false)
    setFollowedArtists(null)
    setFollowedArtistsLoading(false)
    setRecentlyPlayed(null)
    await Promise.allSettled([
      api
        .getHomeSection('continue', 10)
        .then((section) =>
          setSections(section.tracks.length ? [section] : []),
        )
        .catch(() => {
          setSections([])
          return api
            .getTracks({ size: 15 })
            .then((data) => setFallbackTracks(data.items))
            .catch(() => setFallbackTracks([]))
        }),
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

  useMainScrollRestore('home')

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

  const handleOpenArtist = useCallback(
    (artist: FollowedArtistItem) => {
      if (onOpenArtist) {
        onOpenArtist(artist.id)
        return
      }
      navigate(`/search?q=${encodeURIComponent(artist.name)}`)
    },
    [navigate, onOpenArtist],
  )

  const hour = new Date().getHours()
  const greeting =
    hour < 18
      ? t('redesign.home.greetingMorning')
      : t('redesign.home.greetingEvening')
  const displayName =
    me?.display_name || me?.first_name || me?.username || brandLabel

  const sectionMap = useMemo(() => {
    const map = new Map<string, HomeSection>()
    if (!sections) return map
    for (const s of sections) {
      if (s?.section_type) {
        map.set(s.section_type, s)
      }
    }
    return map
  }, [sections])

  const topSlotSection = useMemo(() => {
    const priority = [
      'continue',
      'personalized',
      'user_choice',
      'popular',
    ] as const
    return priority
      .map((key) => sectionMap.get(key))
      .find((s) => s && s.tracks.length > 0)
  }, [sectionMap])

  const topSlotKey = topSlotSection?.section_type ?? null

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
        ? resolveSectionTitle(featuredSource, t)
        : t('redesign.home.heroSignalRadio'))
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
  const [heroCoverFailed, setHeroCoverFailed] = useState(false)

  useEffect(() => {
    setHeroCoverFailed(false)
  }, [featuredTrack?.cover_key])

  const genreTrackCount = (n: number) =>
    t('artist.catalog_release_card_tracks_other', { count: n })

  const filteredRecent = useMemo(() => {
    if (!recentlyPlayed) return null
    const continueIds = new Set(
      (sectionMap.get('continue')?.tracks ?? []).map((tr) => tr.id),
    )
    return recentlyPlayed.filter((tr) => !continueIds.has(tr.id))
  }, [recentlyPlayed, sectionMap])

  const allEmpty =
    sections !== null &&
    sections.length === 0 &&
    fallbackTracks !== null &&
    fallbackTracks.length === 0 &&
    recentlyPlayed !== null &&
    recentlyPlayed.length === 0 &&
    genreMixes !== null &&
    followedArtists !== null

  return (
    <section
      id="view-home"
      className="view active dh-home"
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
          headerStuck ? 'dh-topbar is-stuck' : 'dh-topbar'
        }
      >
        <div className="dh-topbar__greeting">
          <span className="dh-topbar__label">{greeting}</span>
          <h1 className="dh-topbar__title">{displayName}</h1>
        </div>
        <NotificationBell />
      </header>

      <m.div
        className="dh-stack"
        initial="hidden"
        animate="visible"
        variants={VARIANTS_FADE_UP}
      >
        {featuredTrack ? (
          <article className="dh-hero" aria-label={featuredTrack.title}>
            <button
              type="button"
              className="dh-hero__cover"
              onClick={() => void handlePlay(featuredTrack)}
              aria-label={t('redesign.home.heroPlay')}
            >
              {heroCoverSrc && !heroCoverFailed ? (
                <img
                  src={heroCoverSrc}
                  srcSet={heroCoverSrcSet}
                  sizes="(min-width: 768px) 320px, 80vw"
                  alt=""
                  onError={() => setHeroCoverFailed(true)}
                />
              ) : (
                <div className="dh-hero__cover-ph">
                  <Icon name="music" size={36} />
                </div>
              )}
              <span className="dh-hero__play" aria-hidden>
                <Icon name="play" size={20} />
              </span>
            </button>
            <div className="dh-hero__copy">
              <span className="dh-hero__eyebrow">
                {featuredEyebrow}
              </span>
              <h2 className="dh-hero__title">
                {featuredTrack.title ||
                  t('redesign.home.untitled')}
              </h2>
              {featuredTrack.artist && (
                <p
                  className={
                    desktopFine
                      ? 'dh-hero__artist dh-hero__artist--nav'
                      : 'dh-hero__artist'
                  }
                  onClick={
                    desktopFine && featuredTrack.artist
                      ? () => {
                          void goArtistByName(
                            featuredTrack.artist,
                          )
                        }
                      : undefined
                  }
                >
                  {featuredTrack.artist}
                </p>
              )}
              <div className="dh-hero__actions">
                <MotionPress
                  className="dh-btn dh-btn--primary"
                  onClick={() => {
                    void handlePlay(featuredTrack)
                  }}
                >
                  <Icon name="play" size={16} />
                  <span>{t('redesign.home.heroPlay')}</span>
                </MotionPress>
                <MotionPress
                  className="dh-btn dh-btn--secondary"
                  onClick={() => {
                    void handleStartRadioFromHomeRecommendations(
                      'home_start_radio',
                    )
                  }}
                >
                  <Icon name="radio" size={16} />
                  <span>{t('redesign.home.heroRadio')}</span>
                </MotionPress>
              </div>
            </div>
          </article>
        ) : loadingFeatured ? (
          <div className="dh-hero" aria-hidden>
            <div className="dh-skel dh-skel--hero" />
            <div className="dh-hero__copy" style={{ gap: 12 }}>
              <div
                className="dh-skel dh-skel--line"
                style={{ width: 80 }}
              />
              <div
                className="dh-skel dh-skel--line-lg"
                style={{ width: '70%' }}
              />
              <div
                className="dh-skel dh-skel--line"
                style={{ width: '40%' }}
              />
            </div>
          </div>
        ) : null}

        <HomeQuickShortcuts
          onStartRadio={() => {
            void handleStartRadioFromHomeRecommendations(
              'home_start_radio',
            )
          }}
        />

        {sections === null ? (
          <section className="dh-section">
            <DhSectionHead
              title={t('redesign.home.sectionContinue')}
              moreLabel={t('redesign.home.more')}
            />
            <div className="dh-scroller" aria-hidden>
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="dh-skel dh-skel--tile" />
              ))}
            </div>
          </section>
        ) : (
          topSlotSection && (
            <DhTileRow
              title={resolveSectionTitle(topSlotSection, t)}
              tracks={topSlotSection.tracks}
              onPlay={handlePlay}
              moreLabel={t('redesign.home.more')}
              ariaLabel={resolveSectionTitle(topSlotSection, t)}
            />
          )
        )}

        {promoHero && promoHero.length > 0 && (
          <div className="dh-promo">
            <PromotionHero
              items={promoHero}
              onSelect={handlePromotionSelect}
            />
          </div>
        )}

        {genreMixes === null ? (
          <section
            ref={genreMixesSentinelRef}
            className="dh-section"
          >
            <DhSectionHead
              title={t('redesign.home.sectionGenreMixes')}
              moreLabel={t('redesign.home.more')}
            />
            <div className="dh-scroller" aria-hidden>
              {[1, 2, 3].map((i) => (
                <div key={i} className="dh-skel dh-skel--tile" />
              ))}
            </div>
          </section>
        ) : genreMixes.length > 0 ? (
          <section
            className="dh-section"
            aria-label={t('redesign.home.sectionGenreMixes')}
          >
            <DhSectionHead
              title={t('redesign.home.sectionGenreMixes')}
              moreLabel={t('redesign.home.more')}
            />
            <div className="dh-scroller" role="list">
              {genreMixes.map((mix) => (
                <div role="listitem" key={mix.genre}>
                  <DhMixCard
                    mix={mix}
                    countLabel={genreTrackCount(mix.tracks.length)}
                    onOpen={() =>
                      navigate(
                        `/genre-mix/${encodeURIComponent(
                          mix.genre,
                        )}`,
                      )
                    }
                    onPlay={handlePlayAll}
                    listenAria={t('redesign.home.mixPlayAll')}
                  />
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {filteredRecent === null ? (
          <section className="dh-section">
            <DhSectionHead
              title={t('redesign.home.sectionRecent')}
              moreLabel={t('redesign.home.more')}
            />
            <div className="dh-scroller" aria-hidden>
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="dh-skel dh-skel--tile" />
              ))}
            </div>
          </section>
        ) : filteredRecent.length > 0 ? (
          <DhTileRow
            title={t('redesign.home.sectionRecent')}
            tracks={filteredRecent}
            onPlay={handlePlay}
            moreLabel={t('redesign.home.more')}
            ariaLabel={t('redesign.home.sectionRecent')}
          />
        ) : null}

        {followedArtists === null ? (
          <section
            ref={followedArtistsSentinelRef}
            className="dh-section"
          >
            <DhSectionHead
              title={t('redesign.home.sectionSubscriptions')}
              moreLabel={t('redesign.home.more')}
            />
            <div className="dh-scroller" aria-hidden>
              {[1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className="dh-skel dh-skel--avatar"
                />
              ))}
            </div>
          </section>
        ) : followedArtists.length > 0 ? (
          <section
            className="dh-section"
            aria-label={t('redesign.home.sectionSubscriptions')}
          >
            <DhSectionHead
              title={t('redesign.home.sectionSubscriptions')}
              moreLabel={t('redesign.home.more')}
            />
            <div className="dh-scroller" role="list">
              {followedArtists.map((artist) => (
                <div role="listitem" key={artist.id}>
                  <DhArtistChip
                    artist={artist}
                    onOpen={handleOpenArtist}
                  />
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {sections &&
          HOME_LAZY_SECTIONS.filter(
            ({ key }) => key !== topSlotKey,
          ).map(({ key, morePath }) => (
            <DhLazyTileRow
              key={key}
              sectionKey={key}
              initialSection={sectionMap.get(key) ?? null}
              fallbackTitle={t('redesign.home.sectionTracks')}
              onLoaded={upsertHomeSection}
              onPlay={handlePlay}
              onMore={
                morePath ? () => navigate(morePath) : undefined
              }
              moreLabel={t('redesign.home.more')}
            />
          ))}

        {(sections === null || sections.length === 0) &&
          fallbackTracks !== null &&
          fallbackTracks.length > 0 && (
            <DhTileRow
              title={t('redesign.home.sectionTracks')}
              tracks={fallbackTracks}
              onPlay={handlePlay}
              moreLabel={t('redesign.home.more')}
              ariaLabel={t('redesign.home.sectionTracks')}
            />
          )}

        {promoSection && promoSection.length > 0 && (
          <div className="dh-promo">
            <PromotionSection
              items={promoSection}
              surface="section"
              title={t(
                'redesign.home.sectionPromoted',
                'Рекомендуем',
              )}
              onSelect={handlePromotionSelect}
            />
          </div>
        )}

        {allEmpty && (
          <div className="dh-empty">
            <div className="dh-empty__icon" aria-hidden>
              <Icon name="music" size={28} />
            </div>
            <div className="dh-empty__title">
              {t('redesign.home.emptyTitle')}
            </div>
            <p className="dh-empty__hint">
              {t('redesign.home.emptyHint')}
            </p>
            <div className="dh-empty__actions">
              <MotionPress
                className="dh-btn dh-btn--primary"
                onClick={() => {
                  void handleStartFirstSession()
                }}
              >
                <Icon name="play" size={16} />
                <span>{t('redesign.home.emptyStart')}</span>
              </MotionPress>
              <MotionPress
                className="dh-btn dh-btn--secondary"
                onClick={() => navigate('/radio')}
              >
                <Icon name="radio" size={16} />
                <span>{t('redesign.home.emptyRadio')}</span>
              </MotionPress>
              <MotionPress
                className="dh-btn dh-btn--ghost"
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
