import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { TrackList } from '@/components/TrackList/TrackList'
import { TrackCard } from '@/components/TrackCard/TrackCard'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { api } from '@/lib/api'
import { usePlayerActions } from '@/store/PlayerContext'
import { useLikes } from '@/store/LikesContext'
import { useDebounce } from '@/hooks/useDebounce'
import { Icon } from '@/components/Icon/Icon'
import type {
  ArtistInfo,
  BCSearchResult,
  DiscoverResponse,
  Playlist,
  PlaylistWithTracks,
  SCSearchResult,
  SearchSuggestItem,
  Track,
  YTSearchResult,
} from '@/types/api'

type SearchViewProps = {
  onOpenArtist?: (id: number) => void
}

type SearchTab =
  | 'all'
  | 'tracks'
  | 'artists'
  | 'playlists'
  | 'genres'

const SEARCH_DEBOUNCE_MS = 300
const GENRES_PAGE_SIZE = 24

function normalizeGenre(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-zа-я0-9]+/gi, ' ')
    .trim()
    .replace(/\s+/g, ' ')
}

function resolveCanonicalGenre(
  value: string,
  genres: string[],
): string {
  const trimmed = value.trim()
  if (!trimmed || genres.length === 0) {
    return trimmed
  }
  const exact = genres.find(
    (genre) => genre.toLowerCase() === trimmed.toLowerCase(),
  )
  if (exact) return exact
  const normalized = normalizeGenre(trimmed)
  if (!normalized) return trimmed
  const byNormalized = genres.find(
    (genre) => normalizeGenre(genre) === normalized,
  )
  return byNormalized ?? trimmed
}

function mergeTracksBySuggestOrder(
  items: Track[],
  suggest: SearchSuggestItem[],
): Track[] {
  const orderIds = suggest
    .filter((s) => s.kind === 'track')
    .map((s) => s.id)
  if (orderIds.length === 0) return items
  const byId = new Map(items.map((t) => [t.id, t]))
  const seen = new Set<number>()
  const out: Track[] = []
  for (const id of orderIds) {
    const t = byId.get(id)
    if (t) {
      out.push(t)
      seen.add(id)
    }
  }
  for (const t of items) {
    if (!seen.has(t.id)) out.push(t)
  }
  return out
}

function formatDuration(secs: number): string {
  return `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`
}

export function SearchView({ onOpenArtist }: SearchViewProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { playTrack } = usePlayerActions()
  const { toggleLike } = useLikes()

  const [query, setQuery] = useState('')
  const [genreFilter, setGenreFilter] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<SearchTab>('all')

  const [tracks, setTracks] = useState<Track[] | null | 'idle'>('idle')
  const [scResults, setSCResults] = useState<SCSearchResult[]>([])
  const [ytResults, setYtResults] = useState<YTSearchResult[]>([])
  const [bcResults, setBcResults] = useState<BCSearchResult[]>([])
  const [catalogArtists, setCatalogArtists] = useState<ArtistInfo[]>([])
  const [catalogPlaylists, setCatalogPlaylists] = useState<Playlist[]>([])
  const [catalogGenres, setCatalogGenres] = useState<string[]>([])
  const [allGenres, setAllGenres] = useState<string[]>([])
  const [genreSearchTerm, setGenreSearchTerm] = useState('')
  const [genresVisible, setGenresVisible] = useState(
    GENRES_PAGE_SIZE,
  )

  const [importedSC, setImportedSC] = useState<Record<string, Track>>({})
  const [importedYT, setImportedYT] = useState<Record<string, Track>>({})
  const [importedBC, setImportedBC] = useState<Record<string, Track>>({})
  const [importing, setImporting] = useState<string | null>(null)
  const [importingYt, setImportingYt] = useState<string | null>(null)
  const [importingBc, setImportingBc] = useState<string | null>(null)

  const [discover, setDiscover] = useState<DiscoverResponse | null>(null)
  const [discoverLoading, setDiscoverLoading] = useState(false)
  const [featuredPlaylists, setFeaturedPlaylists] = useState<
    PlaylistWithTracks[] | null
  >(null)
  const [searchTotal, setSearchTotal] = useState(0)

  const debouncedQuery = useDebounce(query, SEARCH_DEBOUNCE_MS)
  const inputRef = useRef<HTMLInputElement>(null)
  const requestSeqRef = useRef(0)
  const activeGenreTerm = useMemo(() => {
    if (genreFilter && genreFilter.trim()) {
      return genreFilter.trim()
    }
    if (activeTab === 'genres' && debouncedQuery.trim()) {
      return debouncedQuery.trim()
    }
    return null
  }, [genreFilter, activeTab, debouncedQuery])

  const [history, setHistory] = useState<string[]>(() => {
    try {
      return JSON.parse(
        localStorage.getItem('search-history') || '[]',
      ) as string[]
    } catch {
      return []
    }
  })

  const saveToHistory = (q: string) => {
    setHistory((prev) => {
      const next = [q, ...prev.filter((h) => h !== q)].slice(0, 8)
      localStorage.setItem('search-history', JSON.stringify(next))
      return next
    })
  }

  const removeFromHistory = (q: string) => {
    setHistory((prev) => {
      const next = prev.filter((h) => h !== q)
      localStorage.setItem('search-history', JSON.stringify(next))
      return next
    })
  }

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    let cancelled = false
    setDiscoverLoading(true)
    void Promise.all([
      api.getDiscover(10, 8).catch(() => null),
      api.getFeaturedPlaylists(8).catch(() => []),
    ])
      .then(([d, pls]) => {
        if (cancelled) return
        setDiscover(d)
        setFeaturedPlaylists(pls)
      })
      .finally(() => {
        if (!cancelled) setDiscoverLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (genreFilter) {
      setActiveTab('genres')
      setGenreSearchTerm(genreFilter)
    }
  }, [genreFilter])

  useEffect(() => {
    if (activeTab !== 'genres') return
    setGenresVisible(GENRES_PAGE_SIZE)
  }, [activeTab, genreSearchTerm, genreFilter])

  useEffect(() => {
    if (activeTab !== 'genres') return
    if (allGenres.length > 0) return
    let cancelled = false
    void api
      .getTrackGenres()
      .then((genres) => {
        if (cancelled) return
        const sortedGenres = [...genres].sort((a, b) =>
          a.localeCompare(b, 'ru', {
            sensitivity: 'base',
          }),
        )
        setAllGenres(sortedGenres)
      })
      .catch(() => {
        if (!cancelled) setAllGenres([])
      })
    return () => {
      cancelled = true
    }
  }, [activeTab, allGenres.length])

  useEffect(() => {
    if (!activeGenreTerm) return
    const reqId = ++requestSeqRef.current
    setTracks(null)
    setSearchTotal(0)
    setSCResults([])
    setYtResults([])
    setBcResults([])
    setCatalogArtists([])
    setCatalogPlaylists([])
    setCatalogGenres([])
    let cancelled = false
    void (async () => {
      const genres = await api.getTrackGenres().catch(
        () => [] as string[],
      )
      const canonicalGenre = resolveCanonicalGenre(
        activeGenreTerm,
        genres,
      )
      let internal = await api
        .getTracks({
          genre: canonicalGenre || activeGenreTerm,
          size: 30,
        })
        .catch(() => ({
          items: [] as Track[],
          total: 0,
          page: 1,
          size: 30,
        }))
      if (internal.total === 0) {
        internal = await api
          .getTracks({
            q: canonicalGenre || activeGenreTerm,
            size: 30,
          })
          .catch(() => internal)
      }
      if (
        cancelled ||
        reqId !== requestSeqRef.current
      ) {
        return
      }
      const sortedGenres = [...genres].sort((a, b) =>
        a.localeCompare(b, 'ru', { sensitivity: 'base' }),
      )
      setTracks(internal.items)
      setSearchTotal(internal.total)
      setCatalogGenres(sortedGenres)
      setAllGenres(sortedGenres)
      if (
        canonicalGenre &&
        canonicalGenre !== genreFilter
      ) {
        setGenreFilter(canonicalGenre)
        setQuery(canonicalGenre)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [activeGenreTerm])

  useEffect(() => {
    if (activeGenreTerm) {
      return
    }
    if (!debouncedQuery.trim()) {
      requestSeqRef.current += 1
      setTracks('idle')
      setSearchTotal(0)
      setSCResults([])
      setYtResults([])
      setBcResults([])
      setCatalogArtists([])
      setCatalogPlaylists([])
      setCatalogGenres([])
      return
    }
    setTracks(null)
    setSearchTotal(0)
    setSCResults([])
    setYtResults([])
    setBcResults([])
    setCatalogArtists([])
    setCatalogPlaylists([])
    setCatalogGenres([])
    const reqId = ++requestSeqRef.current
    let cancelled = false
    const q = debouncedQuery
    const emptySuggest = { items: [] as SearchSuggestItem[] }

    api
      .searchSoundCloud(q, 8)
      .then((sc) => {
        if (!cancelled) setSCResults(sc)
      })
      .catch(() => {
        if (!cancelled) setSCResults([])
      })
    api
      .searchYouTube(q, 8)
      .then((yt) => {
        if (!cancelled) setYtResults(yt)
      })
      .catch(() => {
        if (!cancelled) setYtResults([])
      })
    api
      .searchBandcamp(q, 8)
      .then((bc) => {
        if (!cancelled) setBcResults(bc)
      })
      .catch(() => {
        if (!cancelled) setBcResults([])
      })

    api
      .getPlaylists()
      .then((pls) => {
        if (cancelled) return
        const lq = q.toLowerCase()
        setCatalogPlaylists(
          pls.filter((p) => p.name.toLowerCase().includes(lq)),
        )
      })
      .catch(() => {
        if (!cancelled) setCatalogPlaylists([])
      })

    api
      .getTrackGenres()
      .then((genres) => {
        if (cancelled) return
        const lq = q.toLowerCase()
        setCatalogGenres(
          genres.filter((g) => g.toLowerCase().includes(lq)),
        )
      })
      .catch(() => {
        if (!cancelled) setCatalogGenres([])
      })

    void (async () => {
      const [internal, sug, artistsRes] = await Promise.all([
        api
          .getTracks({
            q,
            size: 30,
          })
          .catch(() => ({
            items: [] as Track[],
            total: 0,
            page: 1,
            size: 30,
          })),
        api.searchSuggest(q, 12).catch(() => emptySuggest),
        api
          .getArtists(q, 20)
          .catch(() => ({
            items: [] as ArtistInfo[],
            total: 0,
          })),
      ])
      if (
        cancelled ||
        reqId !== requestSeqRef.current
      ) {
        return
      }
      setSearchTotal(internal.total)
      const have = new Set(internal.items.map((t) => t.id))
      const fromSuggest = sug.items
        .filter((i) => i.kind === 'track')
        .map((i) => i.id)
      const missing = fromSuggest.filter((id) => !have.has(id))
      const extra: Track[] = []
      if (missing.length > 0) {
        const loaded = await Promise.all(
          missing.map((id) => api.getTrack(id).catch(() => null)),
        )
        for (const t of loaded) {
          if (t) extra.push(t)
        }
      }
      if (
        cancelled ||
        reqId !== requestSeqRef.current
      ) {
        return
      }
      const combined = [...internal.items, ...extra]
      const merged = mergeTracksBySuggestOrder(combined, sug.items)
      setTracks(merged)
      setCatalogArtists(artistsRes.items)
    })()
    return () => {
      cancelled = true
    }
  }, [debouncedQuery, activeGenreTerm])

  const ensureImported = async (
    result: SCSearchResult,
  ): Promise<Track | null> => {
    if (importedSC[result.sc_url]) return importedSC[result.sc_url]
    if (importing === result.sc_url) return null
    setImporting(result.sc_url)
    try {
      const track = await api.importSCTrack(result.sc_url, true)
      setImportedSC((prev) => ({ ...prev, [result.sc_url]: track }))
      return track
    } catch {
      return null
    } finally {
      setImporting(null)
    }
  }

  const ensureImportedYT = async (
    result: YTSearchResult,
  ): Promise<Track | null> => {
    if (importedYT[result.video_id]) return importedYT[result.video_id]
    if (importingYt === result.video_id) return null
    setImportingYt(result.video_id)
    try {
      const track = await api.importYouTubeTrack(result.watch_url, true)
      setImportedYT((prev) => ({
        ...prev,
        [result.video_id]: track,
      }))
      return track
    } catch {
      return null
    } finally {
      setImportingYt(null)
    }
  }

  const ensureImportedBC = async (
    result: BCSearchResult,
  ): Promise<Track | null> => {
    if (importedBC[result.track_url]) return importedBC[result.track_url]
    if (importingBc === result.track_url) return null
    setImportingBc(result.track_url)
    try {
      const track = await api.importBandcampTrack(result.track_url, true)
      setImportedBC((prev) => ({
        ...prev,
        [result.track_url]: track,
      }))
      return track
    } catch {
      return null
    } finally {
      setImportingBc(null)
    }
  }

  const handlePlaySC = async (r: SCSearchResult) => {
    const track = await ensureImported(r)
    if (track) await playTrack(track)
  }
  const handlePlayYT = async (r: YTSearchResult) => {
    const track = await ensureImportedYT(r)
    if (track) await playTrack(track)
  }
  const handlePlayBC = async (r: BCSearchResult) => {
    const track = await ensureImportedBC(r)
    if (track) await playTrack(track)
  }

  const handleLikeSC = async (
    e: React.MouseEvent,
    r: SCSearchResult,
  ) => {
    e.stopPropagation()
    const track = await ensureImported(r)
    if (track) await toggleLike(track.id)
  }
  const handleLikeYT = async (
    e: React.MouseEvent,
    r: YTSearchResult,
  ) => {
    e.stopPropagation()
    const track = await ensureImportedYT(r)
    if (track) await toggleLike(track.id)
  }
  const handleLikeBC = async (
    e: React.MouseEvent,
    r: BCSearchResult,
  ) => {
    e.stopPropagation()
    const track = await ensureImportedBC(r)
    if (track) await toggleLike(track.id)
  }

  const clearSearch = () => {
    setQuery('')
    setGenreFilter(null)
    setSearchTotal(0)
    setTracks('idle')
    setSCResults([])
    setYtResults([])
    setBcResults([])
    setCatalogArtists([])
    setCatalogPlaylists([])
    setCatalogGenres([])
    inputRef.current?.focus()
  }

  const isSearching = tracks !== 'idle'

  const idleExploreHasSurface = useMemo(() => {
    const featOk =
      featuredPlaylists !== null && featuredPlaylists.length > 0
    if (!discover) return featOk
    return (
      featOk ||
      discover.genre_cards.length > 0 ||
      discover.recent_genres.length > 0 ||
      discover.suggested_artists.length > 0 ||
      discover.trending_tracks.length > 0
    )
  }, [discover, featuredPlaylists])

  const baseGenreOptions = useMemo(() => {
    const seen = new Set<string>()
    const out: string[] = []
    const addGenre = (genre: string | null) => {
      if (!genre) return
      const trimmed = genre.trim()
      if (!trimmed) return
      if (seen.has(trimmed)) return
      seen.add(trimmed)
      out.push(trimmed)
    }
    addGenre(genreFilter)
    for (const genre of allGenres) {
      addGenre(genre)
    }
    return out
  }, [allGenres, genreFilter])

  const filteredGenreOptions = useMemo(() => {
    const term = genreSearchTerm.trim().toLowerCase()
    if (!term) return baseGenreOptions
    return baseGenreOptions.filter((genre) =>
      genre.toLowerCase().includes(term),
    )
  }, [baseGenreOptions, genreSearchTerm])

  const visibleGenreOptions = useMemo(
    () => filteredGenreOptions.slice(0, genresVisible),
    [filteredGenreOptions, genresVisible],
  )

  const hasMoreGenreOptions =
    filteredGenreOptions.length > genresVisible

  const tabHasResults = useMemo(() => {
    if (!Array.isArray(tracks)) return true
    const genreOptionsCount = filteredGenreOptions.length
    switch (activeTab) {
      case 'all':
        return (
          tracks.length > 0 ||
          catalogArtists.length > 0 ||
          catalogGenres.length > 0 ||
          catalogPlaylists.length > 0 ||
          scResults.length > 0 ||
          ytResults.length > 0 ||
          bcResults.length > 0
        )
      case 'tracks':
        return (
          tracks.length > 0 ||
          scResults.length > 0 ||
          ytResults.length > 0 ||
          bcResults.length > 0
        )
      case 'artists':
        return catalogArtists.length > 0
      case 'playlists':
        return catalogPlaylists.length > 0
      case 'genres':
        return (
          genreOptionsCount > 0 ||
          Boolean(activeGenreTerm && tracks.length > 0)
        )
      default:
        return false
    }
  }, [
    activeTab,
    tracks,
    catalogArtists,
    catalogGenres,
    activeGenreTerm,
    filteredGenreOptions,
    catalogPlaylists,
    scResults,
    ytResults,
    bcResults,
  ])

  return (
    <section id="view-search" className="view active">
      <div className="search-sticky">
        <div className="search-bar">
          <span className="search-icon">
            <Icon name="search" size={16} />
          </span>
          <input
            ref={inputRef}
            id="search-input"
            type="search"
            enterKeyHint="search"
            placeholder={t('search.placeholder')}
            autoComplete="off"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setGenreFilter(null)
            }}
            onKeyDown={(e) => {
              if (e.key !== 'Enter') return
              e.preventDefault()
              const q = e.currentTarget.value.trim()
              if (q) saveToHistory(q)
            }}
          />
          {query && (
            <button
              type="button"
              className="icon-btn"
              onClick={clearSearch}
            >
              <Icon name="x" size={16} />
            </button>
          )}
        </div>

        {isSearching && (
          <div className="search-tabs" role="tablist">
            {(
              [
                ['all', t('search.tabAll')],
                ['tracks', t('search.tabTracks')],
                ['artists', t('search.tabArtists')],
                ['playlists', t('search.tabPlaylists')],
                ['genres', t('search.tabGenres')],
              ] as [SearchTab, string][]
            ).map(([tab, label]) => (
              <button
                key={tab}
                role="tab"
                aria-selected={activeTab === tab}
                className={`search-tab${activeTab === tab ? ' search-tab--active' : ''}`}
                onClick={() => setActiveTab(tab)}
                type="button"
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      {tracks === 'idle' && (
        <>
          {history.length > 0 && (
            <div className="search-history">
              <p className="search-section-label">
                {t('search.recent')}
              </p>
              {history.map((h) => (
                <div
                  key={h}
                  className="search-history-item"
                  onClick={() => {
                    setQuery(h)
                    setGenreFilter(null)
                  }}
                >
                  <Icon name="search" size={14} />
                  <span>{h}</span>
                  <button
                    className="icon-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      removeFromHistory(h)
                    }}
                    type="button"
                  >
                    <Icon name="x" size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {discoverLoading && (
            <div className="search-discover-loading">
              <div className="loader" />
            </div>
          )}

          {!discoverLoading && (
            <div className="search-discover">
              {featuredPlaylists !== null &&
                featuredPlaylists.length > 0 && (
                  <div className="search-discover-section">
                    <p className="search-section-label">
                      {t('search.featuredPlaylists')}
                    </p>
                    <div className="search-playlist-list">
                      {featuredPlaylists.map((p) => (
                        <div
                          key={p.id}
                          role="button"
                          tabIndex={0}
                          className="search-playlist-row"
                          aria-label={t(
                            'search.openPlaylistAria',
                            { name: p.name },
                          )}
                          onClick={() =>
                            navigate(`/playlist/${p.id}`)
                          }
                          onKeyDown={(e) => {
                            if (
                              e.key === 'Enter' ||
                              e.key === ' '
                            ) {
                              e.preventDefault()
                              navigate(`/playlist/${p.id}`)
                            }
                          }}
                        >
                          <div className="search-playlist-cover">
                            {p.cover_key ? (
                              <CoverImage
                                coverKey={p.cover_key}
                              />
                            ) : (
                              <Icon name="list" size={18} />
                            )}
                          </div>
                          <div className="search-playlist-info">
                            <p className="search-playlist-name">
                              {p.name}
                            </p>
                            <p className="search-playlist-meta">
                              {p.playlist_type !== 'user'
                                ? t('search.editorialBadge')
                                : p.is_public
                                  ? t('search.publicBadge')
                                  : t('search.privateBadge')}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              {discover && discover.genre_cards.length > 0 && (
                <div className="search-discover-section">
                  <p className="search-section-label">
                    {t('search.discoverGenres')}
                  </p>
                  <div className="search-genre-grid">
                    {discover.genre_cards
                      .slice(0, 8)
                      .map((card) => (
                        <button
                          key={card.genre}
                          type="button"
                          className={`search-genre-card${
                            card.cover_key ? '' : ' search-genre-card--skeleton'
                          }`}
                          onClick={() => {
                            setQuery(card.genre)
                            setGenreFilter(card.genre)
                            setActiveTab('genres')
                          }}
                        >
                          {card.cover_key && (
                            <CoverImage
                              coverKey={card.cover_key}
                              className="search-genre-cover"
                            />
                          )}
                          <span className="search-genre-overlay" />
                          <span className="search-genre-name">
                            {card.title}
                          </span>
                          {card.track_count > 0 && (
                            <span className="search-genre-count">
                              {card.track_count}
                            </span>
                          )}
                        </button>
                      ))}
                  </div>
                </div>
              )}

              {discover && discover.recent_genres.length > 0 && (
                <div className="search-discover-section">
                  <p className="search-section-label">
                    {t('search.recentGenres')}
                  </p>
                  <div className="search-genre-chips">
                    {discover.recent_genres.map((g) => (
                      <button
                        key={g}
                        type="button"
                        className="search-genre-chip"
                        onClick={() => {
                          setQuery(g)
                          setGenreFilter(g)
                          setActiveTab('genres')
                        }}
                      >
                        <Icon name="music-note" size={12} />
                        {g}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {discover && discover.suggested_artists.length > 0 && (
                <div className="search-discover-section">
                  <p className="search-section-label">
                    {t('search.discoverArtists')}
                  </p>
                  <div className="search-artist-strip">
                    {discover.suggested_artists.map((a) => (
                      <button
                        key={a.id}
                        type="button"
                        className="search-artist-pill"
                        onClick={() => onOpenArtist?.(a.id)}
                      >
                        <CoverImage
                          coverKey={a.image_key ?? null}
                          className="search-artist-pill__avatar"
                        />
                        <span className="search-artist-pill__name">
                          {a.name}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {discover && discover.trending_tracks.length > 0 && (
                <div className="search-discover-section">
                  <p className="search-section-label">
                    {t('search.discoverTrending')}
                  </p>
                  <TrackList
                    tracks={discover.trending_tracks}
                    emptyMessage=""
                  />
                </div>
              )}

              {history.length === 0 && !idleExploreHasSurface && (
                <div className="search-idle-hint">
                  <Icon name="search" size={32} />
                  <p>{t('search.hint')}</p>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {tracks === null && (
        <div className="search-section">
          <p className="search-section-label">
            {t('search.onPlatform')}
          </p>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="track-card-skeleton shimmer" />
          ))}
        </div>
      )}

      {Array.isArray(tracks) && (
        <>
          {(activeTab === 'all' || activeTab === 'artists') && (
            <div className="search-section">
              <p className="search-section-label">
                {t('search.artists')}
              </p>
              {catalogArtists.length > 0 ? (
                <div className="search-artist-list">
                  {catalogArtists.map((a) => (
                    <div
                      key={`catalog-artist-${a.id}`}
                      className="search-artist-row"
                      role="button"
                      tabIndex={0}
                      aria-label={a.name}
                      onClick={() => onOpenArtist?.(a.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          onOpenArtist?.(a.id)
                        }
                      }}
                    >
                      <CoverImage
                        coverKey={a.image_key ?? null}
                        className="search-artist-row__avatar"
                      />
                      <div className="search-artist-row__info">
                        <p className="search-artist-row__name">
                          {a.name}
                        </p>
                        <p className="search-artist-row__badge">
                          {t('search.catalogArtistBadge')}
                        </p>
                      </div>
                      <Icon
                        name="chevron"
                        size={16}
                        className="search-artist-row__chevron"
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <p className="search-catalog-empty">
                  {t('search.artistsEmpty')}
                </p>
              )}
            </div>
          )}

          {(activeTab === 'all' || activeTab === 'tracks') && (
            <div className="search-section">
              <p className="search-section-label">
                {t('search.platformTracks')}
              </p>
              {tracks.length > 0 ? (
                <TrackList tracks={tracks} emptyMessage="" />
              ) : (
                <p className="search-catalog-empty">
                  {t('search.emptyCatalogHint')}
                </p>
              )}
            </div>
          )}

          {((activeTab === 'all' &&
            catalogPlaylists.length > 0) ||
            activeTab === 'playlists') && (
            <div className="search-section">
              <p className="search-section-label">
                {t('search.playlists')}
              </p>
              {catalogPlaylists.length > 0 ? (
                <div className="search-playlist-list">
                  {catalogPlaylists.map((p) => (
                    <div
                      key={p.id}
                      role="button"
                      tabIndex={0}
                      className="search-playlist-row"
                      aria-label={t(
                        'search.openPlaylistAria',
                        { name: p.name },
                      )}
                      onClick={() =>
                        navigate(`/playlist/${p.id}`)
                      }
                      onKeyDown={(e) => {
                        if (
                          e.key === 'Enter' ||
                          e.key === ' '
                        ) {
                          e.preventDefault()
                          navigate(`/playlist/${p.id}`)
                        }
                      }}
                    >
                      <div className="search-playlist-cover">
                        {p.cover_key ? (
                          <CoverImage coverKey={p.cover_key} />
                        ) : (
                          <Icon name="list" size={18} />
                        )}
                      </div>
                      <div className="search-playlist-info">
                        <p className="search-playlist-name">
                          {p.name}
                        </p>
                        <p className="search-playlist-meta">
                          {p.playlist_type !== 'user'
                            ? t('search.editorialBadge')
                            : p.is_public
                              ? t('search.publicBadge')
                              : t('search.privateBadge')}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="search-catalog-empty">
                  {t('search.playlistsTabEmpty')}
                </p>
              )}
            </div>
          )}

          {((activeTab === 'all' &&
            (catalogGenres.length > 0 || Boolean(genreFilter))) ||
            activeTab === 'genres') && (
            <div className="search-section">
              <p className="search-section-label">
                {t('search.discoverGenres')}
              </p>
              {(catalogGenres.length > 0 || activeGenreTerm) ? (
                <>
                  <div className="search-bar" style={{ marginBottom: 8 }}>
                    <span className="search-icon">
                      <Icon name="search" size={16} />
                    </span>
                    <input
                      type="search"
                      enterKeyHint="search"
                      placeholder={t('search.genresSearchPlaceholder')}
                      autoComplete="off"
                      value={genreSearchTerm}
                      onChange={(e) => {
                        const value = e.target.value
                        setGenreSearchTerm(value)
                        if (
                          genreFilter &&
                          value.trim() !== genreFilter
                        ) {
                          setGenreFilter(null)
                        }
                      }}
                    />
                  </div>
                  <div className="search-genre-chips">
                    {visibleGenreOptions.map((g) => (
                      <button
                        key={g}
                        type="button"
                        className="search-genre-chip"
                        onClick={() => {
                          setQuery(g)
                          setGenreSearchTerm(g)
                          setGenreFilter(g)
                          setActiveTab('genres')
                        }}
                      >
                        <Icon name="music-note" size={12} />
                        {g}
                      </button>
                    ))}
                  </div>
                  {hasMoreGenreOptions && (
                    <button
                      type="button"
                      className="search-tab"
                      style={{ marginTop: 8 }}
                      onClick={() =>
                        setGenresVisible(
                          (prev) => prev + GENRES_PAGE_SIZE,
                        )
                      }
                    >
                      {t('common.showMore')}
                    </button>
                  )}
                </>
              ) : (
                <p className="search-catalog-empty">
                  {t('search.genresTabEmpty')}
                </p>
              )}
              {activeTab === 'genres' && activeGenreTerm && (
                <p className="search-catalog-empty" style={{ paddingTop: 8 }}>
                  {t('search.genreTracksCount', {
                    count: searchTotal,
                    genre: activeGenreTerm,
                  })}
                </p>
              )}
              {activeTab === 'genres' && tracks.length > 0 && (
                <TrackList tracks={tracks} emptyMessage="" />
              )}
            </div>
          )}

          {(activeTab === 'all' || activeTab === 'tracks') && (
            <>
              {ytResults.length > 0 && (
                <div className="search-section">
                  <p className="search-section-label">
                    {t('search.ytSection')}
                  </p>
                  {ytResults.map((r) => {
                    const imported = importedYT[r.video_id]
                    if (imported) {
                      return (
                        <TrackCard key={r.video_id} track={imported} />
                      )
                    }
                    return (
                      <div
                        key={r.video_id}
                        className="track-card sc-result"
                        onClick={() => void handlePlayYT(r)}
                      >
                        <CoverImage
                          coverKey={null}
                          externalUrl={r.thumbnail_url}
                        />
                        <div className="track-card-info">
                          <div className="track-card-title-row">
                            <p className="track-card-title" dir="auto">
                              <span className="track-card-title-core">
                                {r.title}
                              </span>
                              {r.artist ? (
                                <span className="track-card-title-artist">
                                  {' · '}
                                  {r.artist}
                                </span>
                              ) : null}
                            </p>
                          </div>
                          <p
                            className="track-card-meta track-card-summary"
                            dir="auto"
                          >
                            {[
                              r.duration_seconds != null &&
                              r.duration_seconds > 0
                                ? formatDuration(
                                    r.duration_seconds,
                                  )
                                : null,
                              'YouTube',
                              t('search.afterAddStream'),
                            ]
                              .filter(Boolean)
                              .join(' · ')}
                          </p>
                        </div>
                        <div
                          className="track-card-actions"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            className="track-card-like"
                            title={t('search.addAndLike')}
                            onClick={(e) => void handleLikeYT(e, r)}
                            disabled={importingYt === r.video_id}
                            type="button"
                          >
                            <Icon name="heart-outline" size={18} />
                          </button>
                          <span className="sc-play-hint sc-play-hint--yt">
                            {importingYt === r.video_id
                              ? '...'
                              : t('search.addAndPlay')}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}

              {bcResults.length > 0 && (
                <div className="search-section">
                  <p className="search-section-label">
                    {t('search.bcSection')}
                  </p>
                  {bcResults.map((r) => {
                    const imported = importedBC[r.track_url]
                    if (imported) {
                      return (
                        <TrackCard
                          key={r.result_id}
                          track={imported}
                        />
                      )
                    }
                    return (
                      <div
                        key={r.result_id}
                        className="track-card sc-result"
                        onClick={() => void handlePlayBC(r)}
                      >
                        <CoverImage
                          coverKey={null}
                          externalUrl={r.artwork_url}
                        />
                        <div className="track-card-info">
                          <div className="track-card-title-row">
                            <p className="track-card-title" dir="auto">
                              <span className="track-card-title-core">
                                {r.title}
                              </span>
                              {r.artist ? (
                                <span className="track-card-title-artist">
                                  {' · '}
                                  {r.artist}
                                </span>
                              ) : null}
                            </p>
                          </div>
                          <p
                            className="track-card-meta track-card-summary"
                            dir="auto"
                          >
                            {[
                              r.duration_seconds != null &&
                              r.duration_seconds > 0
                                ? formatDuration(
                                    r.duration_seconds,
                                  )
                                : null,
                              'Bandcamp',
                              t('search.afterAddStream'),
                            ]
                              .filter(Boolean)
                              .join(' · ')}
                          </p>
                        </div>
                        <div
                          className="track-card-actions"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            className="track-card-like"
                            title={t('search.addAndLike')}
                            onClick={(e) =>
                              void handleLikeBC(e, r)
                            }
                            disabled={
                              importingBc === r.track_url
                            }
                            type="button"
                          >
                            <Icon name="heart-outline" size={18} />
                          </button>
                          <span className="sc-play-hint sc-play-hint--bc">
                            {importingBc === r.track_url
                              ? '...'
                              : t('search.addAndPlay')}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}

              {scResults.length > 0 && (
                <div className="search-section">
                  <p className="search-section-label">
                    {t('search.scSection')}
                  </p>
                  {scResults.map((r) => {
                    const imported = importedSC[r.sc_url]
                    if (imported) {
                      return (
                        <TrackCard key={r.sc_id} track={imported} />
                      )
                    }
                    return (
                      <div
                        key={r.sc_id}
                        className="track-card sc-result"
                        onClick={() => void handlePlaySC(r)}
                      >
                        <CoverImage
                          coverKey={null}
                          externalUrl={r.artwork_url}
                        />
                        <div className="track-card-info">
                          <div className="track-card-title-row">
                            <p className="track-card-title" dir="auto">
                              <span className="track-card-title-core">
                                {r.title}
                              </span>
                              {r.artist ? (
                                <span className="track-card-title-artist">
                                  {' · '}
                                  {r.artist}
                                </span>
                              ) : null}
                            </p>
                          </div>
                          <p
                            className="track-card-meta track-card-summary"
                            dir="auto"
                          >
                            {[
                              r.duration_seconds != null &&
                              r.duration_seconds > 0
                                ? formatDuration(
                                    r.duration_seconds,
                                  )
                                : null,
                              'SoundCloud',
                              t('search.afterAddStream'),
                            ]
                              .filter(Boolean)
                              .join(' · ')}
                          </p>
                        </div>
                        <div
                          className="track-card-actions"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            className="track-card-like"
                            title={t('search.addAndLike')}
                            onClick={(e) =>
                              void handleLikeSC(e, r)
                            }
                            disabled={
                              importing === r.sc_url
                            }
                            type="button"
                          >
                            <Icon name="heart-outline" size={18} />
                          </button>
                          <span className="sc-play-hint">
                            {importing === r.sc_url
                              ? '...'
                              : t('search.addAndPlay')}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </>
          )}

          {!tabHasResults && (
            <p className="empty-hint">{t('search.notFound')}</p>
          )}
        </>
      )}
    </section>
  )
}
