import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
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
  SCSearchResult,
  SearchSuggestItem,
  Track,
  YTSearchResult,
} from '@/types/api'

type SearchViewProps = {
  onOpenArtist?: (id: number) => void
}

type SearchTab = 'all' | 'tracks' | 'artists' | 'playlists'

const SEARCH_DEBOUNCE_MS = 300

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
  const { playTrack } = usePlayerActions()
  const { toggleLike } = useLikes()

  const [query, setQuery] = useState('')
  const [activeTab, setActiveTab] = useState<SearchTab>('all')

  const [tracks, setTracks] = useState<Track[] | null | 'idle'>('idle')
  const [scResults, setSCResults] = useState<SCSearchResult[]>([])
  const [ytResults, setYtResults] = useState<YTSearchResult[]>([])
  const [bcResults, setBcResults] = useState<BCSearchResult[]>([])
  const [catalogArtists, setCatalogArtists] = useState<ArtistInfo[]>([])
  const [catalogPlaylists, setCatalogPlaylists] = useState<Playlist[]>([])

  const [importedSC, setImportedSC] = useState<Record<string, Track>>({})
  const [importedYT, setImportedYT] = useState<Record<string, Track>>({})
  const [importedBC, setImportedBC] = useState<Record<string, Track>>({})
  const [importing, setImporting] = useState<string | null>(null)
  const [importingYt, setImportingYt] = useState<string | null>(null)
  const [importingBc, setImportingBc] = useState<string | null>(null)

  const [discover, setDiscover] = useState<DiscoverResponse | null>(null)
  const [discoverLoading, setDiscoverLoading] = useState(false)

  const debouncedQuery = useDebounce(query, SEARCH_DEBOUNCE_MS)
  const inputRef = useRef<HTMLInputElement>(null)

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
    if (!debouncedQuery.trim() && !discover && !discoverLoading) {
      setDiscoverLoading(true)
      api
        .getDiscover(10, 8)
        .then(setDiscover)
        .catch(() => setDiscover(null))
        .finally(() => setDiscoverLoading(false))
    }
  }, [])

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setTracks('idle')
      setSCResults([])
      setYtResults([])
      setBcResults([])
      setCatalogArtists([])
      setCatalogPlaylists([])
      return
    }
    setTracks(null)
    setSCResults([])
    setYtResults([])
    setBcResults([])
    setCatalogArtists([])
    setCatalogPlaylists([])
    saveToHistory(debouncedQuery.trim())
    let cancelled = false
    const q = debouncedQuery
    const emptySuggest = { items: [] as SearchSuggestItem[] }

    api
      .searchSoundCloud(q, 8)
      .then((sc) => { if (!cancelled) setSCResults(sc) })
      .catch(() => { if (!cancelled) setSCResults([]) })
    api
      .searchYouTube(q, 8)
      .then((yt) => { if (!cancelled) setYtResults(yt) })
      .catch(() => { if (!cancelled) setYtResults([]) })
    api
      .searchBandcamp(q, 8)
      .then((bc) => { if (!cancelled) setBcResults(bc) })
      .catch(() => { if (!cancelled) setBcResults([]) })

    api
      .getPlaylists()
      .then((pls) => {
        if (cancelled) return
        const lq = q.toLowerCase()
        setCatalogPlaylists(
          pls.filter((p) =>
            p.name.toLowerCase().includes(lq),
          ),
        )
      })
      .catch(() => { if (!cancelled) setCatalogPlaylists([]) })

    void (async () => {
      const [internal, sug, artistsRes] = await Promise.all([
        api
          .getTracks({ q, size: 30 })
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
      if (cancelled) return
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
      if (cancelled) return
      const combined = [...internal.items, ...extra]
      const merged = mergeTracksBySuggestOrder(combined, sug.items)
      setTracks(merged)
      setCatalogArtists(artistsRes.items)
    })()
    return () => { cancelled = true }
  }, [debouncedQuery])

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
    setTracks('idle')
    setSCResults([])
    setYtResults([])
    setBcResults([])
    setCatalogArtists([])
    setCatalogPlaylists([])
    inputRef.current?.focus()
  }

  const isSearching = tracks !== 'idle'
  const hasResults =
    Array.isArray(tracks) &&
    (tracks.length > 0 ||
      catalogArtists.length > 0 ||
      catalogPlaylists.length > 0 ||
      scResults.length > 0 ||
      ytResults.length > 0 ||
      bcResults.length > 0)

  const externalResults = [
    ...scResults.map((r) => ({ type: 'sc' as const, r })),
    ...ytResults.map((r) => ({ type: 'yt' as const, r })),
    ...bcResults.map((r) => ({ type: 'bc' as const, r })),
  ]

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
            onChange={(e) => setQuery(e.target.value)}
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

      {/* Empty state: discover / history */}
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
                  onClick={() => setQuery(h)}
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

          {discover && !discoverLoading && (
            <div className="search-discover">
              {discover.genre_cards.length > 0 && (
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
                          className="search-genre-card"
                          onClick={() => setQuery(card.genre)}
                        >
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

              {discover.recent_genres.length > 0 && (
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
                        onClick={() => setQuery(g)}
                      >
                        {g}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {discover.suggested_artists.length > 0 && (
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

              {discover.trending_tracks.length > 0 && (
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

              {history.length === 0 &&
                discover.genre_cards.length === 0 &&
                discover.trending_tracks.length === 0 && (
                  <div className="search-idle-hint">
                    <Icon name="search" size={32} />
                    <p>{t('search.hint')}</p>
                  </div>
                )}
            </div>
          )}

          {!discover && !discoverLoading && history.length === 0 && (
            <div className="search-idle-hint">
              <Icon name="search" size={32} />
              <p>{t('search.hint')}</p>
            </div>
          )}
        </>
      )}

      {/* Loading skeleton */}
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

      {/* Search results */}
      {Array.isArray(tracks) && (
        <>
          {/* ALL tab or ARTISTS tab */}
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

          {/* ALL tab or TRACKS tab */}
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

          {/* ALL tab or PLAYLISTS tab */}
          {(activeTab === 'all' || activeTab === 'playlists') &&
            catalogPlaylists.length > 0 && (
              <div className="search-section">
                <p className="search-section-label">
                  {t('search.playlists')}
                </p>
                <div className="search-playlist-list">
                  {catalogPlaylists.map((p) => (
                    <div
                      key={p.id}
                      className="search-playlist-row"
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
              </div>
            )}

          {/* External sources — only on ALL or TRACKS tab */}
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
                            <p className="track-card-title">
                              {r.title}
                            </p>
                            <span className="track-badge track-badge-yt">
                              YT
                            </span>
                          </div>
                          <p className="track-card-artist">
                            {r.artist ?? '—'}
                          </p>
                          {r.duration_seconds != null && (
                            <p className="track-card-meta">
                              <span className="sc-duration">
                                {formatDuration(r.duration_seconds)}
                              </span>
                            </p>
                          )}
                          <span className="track-source">
                            {t('search.extSourceLabel')}{' '}
                            <a
                              href={r.watch_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="track-source-link"
                              onClick={(e) => e.stopPropagation()}
                            >
                              YouTube
                            </a>
                          </span>
                          <span className="track-source">
                            {t('search.afterAddStream')}
                          </span>
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
                            <p className="track-card-title">
                              {r.title}
                            </p>
                            <span className="track-badge track-badge-bc">
                              BC
                            </span>
                          </div>
                          <p className="track-card-artist">
                            {r.artist ?? '—'}
                          </p>
                          {r.duration_seconds != null && (
                            <p className="track-card-meta">
                              <span className="sc-duration">
                                {formatDuration(r.duration_seconds)}
                              </span>
                            </p>
                          )}
                          <span className="track-source">
                            {t('search.extSourceLabel')}{' '}
                            <a
                              href={r.track_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="track-source-link"
                              onClick={(e) => e.stopPropagation()}
                            >
                              Bandcamp
                            </a>
                          </span>
                          <span className="track-source">
                            {t('search.afterAddStream')}
                          </span>
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
                            <p className="track-card-title">
                              {r.title}
                            </p>
                            <span className="track-badge track-badge-sc">
                              SC
                            </span>
                          </div>
                          <p className="track-card-artist">
                            {r.artist ?? '—'}
                          </p>
                          {r.duration_seconds != null && (
                            <p className="track-card-meta">
                              <span className="sc-duration">
                                {formatDuration(r.duration_seconds)}
                              </span>
                            </p>
                          )}
                          <span className="track-source">
                            {t('search.extSourceLabel')}{' '}
                            <a
                              href={r.sc_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="track-source-link"
                              onClick={(e) => e.stopPropagation()}
                            >
                              SoundCloud
                            </a>
                          </span>
                          <span className="track-source">
                            {t('search.afterAddStream')}
                          </span>
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

          {!hasResults && (
            <p className="empty-hint">{t('search.notFound')}</p>
          )}
        </>
      )}

      {/* Suppress unused var warning */}
      {externalResults.length === 0 && null}
    </section>
  )
}
