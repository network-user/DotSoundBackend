import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { TrackList } from '@/components/TrackList/TrackList'
import { TrackCard } from '@/components/TrackCard/TrackCard'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { api } from '@/lib/api'
import { usePlayerActions } from '@/store/PlayerContext'
import { useLikes } from '@/store/LikesContext'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import { useDebounce } from '@/hooks/useDebounce'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  SPRING_GENTLE,
  TWEEN_FAST,
  VARIANTS_FADE_UP,
  m,
} from '@/lib/motion'
import type {
  ArtistInfo,
  BCSearchResult,
  SCSearchResult,
  SearchSuggestItem,
  Track,
  YTSearchResult,
} from '@/types/api'

type SearchViewProps = {
  onOpenArtist?: (id: number) => void
}

type EntityFilter = 'all' | 'tracks' | 'artists' | 'external'

const SEARCH_DEBOUNCE_MS = 300

const ENTITY_FILTERS: {
  id: EntityFilter
  labelKey: string
  icon: string
}[] = [
  {
    id: 'all',
    labelKey: 'redesign.library.searchFilterAll',
    icon: 'search',
  },
  {
    id: 'tracks',
    labelKey: 'redesign.library.searchFilterTracks',
    icon: 'music',
  },
  {
    id: 'artists',
    labelKey: 'redesign.library.searchFilterArtists',
    icon: 'users-listeners',
  },
  {
    id: 'external',
    labelKey: 'redesign.library.searchFilterExternal',
    icon: 'link',
  },
]

/** ╨Я╨╛╤А╤П╨┤╨╛╨║ ╤В╤А╨╡╨║╨╛╨▓ ╨╕╨╖ ES suggest ╤Б╨▓╨╡╤А╤Е╤Г, ╨╛╤Б╤В╨░╨╗╤М╨╜╤Л╨╡ тАФ ╨║╨░╨║ ╨▓ ╨▓╤Л╨┤╨░╤З╨╡ getTracks */
function mergeTracksBySuggestOrder(
  items: Track[],
  suggest: SearchSuggestItem[],
): Track[] {
  const orderIds = suggest
    .filter((s) => s.kind === 'track')
    .map((s) => s.id)
  if (orderIds.length === 0) {
    return items
  }
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
    if (!seen.has(t.id)) {
      out.push(t)
    }
  }
  return out
}

export function SearchView({ onOpenArtist }: SearchViewProps) {
  const { t } = useTranslation()
  const { playTrack } = usePlayerActions()
  const { toggleLike } = useLikes()
  const [query, setQuery] = useState('')
  const [tracks, setTracks] = useState<Track[] | null | 'idle'>('idle')
  const [scResults, setSCResults] = useState<SCSearchResult[]>([])
  const [ytResults, setYtResults] = useState<YTSearchResult[]>([])
  const [bcResults, setBcResults] = useState<BCSearchResult[]>([])
  const [importedSC, setImportedSC] = useState<Record<string, Track>>({})
  const [importedYT, setImportedYT] = useState<Record<string, Track>>({})
  const [importedBC, setImportedBC] = useState<Record<string, Track>>({})
  const [importing, setImporting] = useState<string | null>(null)
  const [importingYt, setImportingYt] = useState<string | null>(null)
  const [importingBc, setImportingBc] = useState<string | null>(null)
  /** ╨Ъ╨░╤В╨░╨╗╨╛╨╢╨╜╤Л╨╡ ╨░╤А╤В╨╕╤Б╤В╤Л (╤В╨░ ╨╢╨╡ ╤Б╤Г╤Й╨╜╨╛╤Б╤В╤М, ╤З╤В╨╛ ╨▓ ╨║╨░╤А╤В╨╛╤З╨║╨╡ ╤В╤А╨╡╨║╨░) */
  const [catalogArtists, setCatalogArtists] = useState<ArtistInfo[]>([])
  const debouncedQuery = useDebounce(query, SEARCH_DEBOUNCE_MS)
  const inputRef = useRef<HTMLInputElement>(null)
  const [entityFilter, setEntityFilter] =
    useState<EntityFilter>('all')
  const [inputFocused, setInputFocused] = useState(false)

  const searchPrefetchSlice =
    typeof tracks === 'object' && tracks !== null
      ? tracks.slice(0, 3)
      : null
  usePrefetchTracks(searchPrefetchSlice, 'search_results')

  const [history, setHistory] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('search-history') || '[]') } catch { return [] }
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
    if (!debouncedQuery.trim()) {
      setTracks('idle')
      setSCResults([])
      setYtResults([])
      setBcResults([])
      setCatalogArtists([])
      return
    }
    setTracks(null)
    setSCResults([])
    setYtResults([])
    setBcResults([])
    setCatalogArtists([])
    saveToHistory(debouncedQuery.trim())
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

    void (async () => {
      const [internal, sug, artistsRes] = await Promise.all([
        api.getTracks({ q, size: 30 }).catch(() => ({
          items: [] as Track[],
          total: 0,
          page: 1,
          size: 30,
        })),
        api.searchSuggest(q, 12).catch(() => emptySuggest),
        api.getArtists(q, 20).catch(() => ({
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
    return () => {
      cancelled = true
    }
  }, [debouncedQuery])

  const ensureImportedYT = async (
    result: YTSearchResult,
  ): Promise<Track | null> => {
    if (importedYT[result.video_id]) return importedYT[result.video_id]
    if (importingYt === result.video_id) return null
    setImportingYt(result.video_id)
    try {
      const track = await api.importYouTubeTrack(result.watch_url, true)
      setImportedYT((prev) => ({ ...prev, [result.video_id]: track }))
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
      setImportedBC((prev) => ({ ...prev, [result.track_url]: track }))
      return track
    } catch {
      return null
    } finally {
      setImportingBc(null)
    }
  }

  const ensureImported = async (result: SCSearchResult): Promise<Track | null> => {
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

  const handlePlaySC = async (result: SCSearchResult) => {
    const track = await ensureImported(result)
    if (track) await playTrack(track)
  }

  const handlePlayYT = async (result: YTSearchResult) => {
    const track = await ensureImportedYT(result)
    if (track) await playTrack(track)
  }

  const handlePlayBC = async (result: BCSearchResult) => {
    const track = await ensureImportedBC(result)
    if (track) await playTrack(track)
  }

  const handleLikeSC = async (e: React.MouseEvent, result: SCSearchResult) => {
    e.stopPropagation()
    const track = await ensureImported(result)
    if (track) await toggleLike(track.id)
  }

  const handleLikeYT = async (e: React.MouseEvent, result: YTSearchResult) => {
    e.stopPropagation()
    const track = await ensureImportedYT(result)
    if (track) await toggleLike(track.id)
  }

  const handleLikeBC = async (e: React.MouseEvent, result: BCSearchResult) => {
    e.stopPropagation()
    const track = await ensureImportedBC(result)
    if (track) await toggleLike(track.id)
  }

  const clearSearch = () => {
    setQuery('')
    setTracks('idle')
    setSCResults([])
    setYtResults([])
    setBcResults([])
    setCatalogArtists([])
    setEntityFilter('all')
    inputRef.current?.focus()
  }

  const hasActiveQuery = Boolean(debouncedQuery.trim())
  const chipsVisible = hasActiveQuery && tracks !== 'idle'
  const showArtistsBlock =
    hasActiveQuery &&
    (entityFilter === 'all' || entityFilter === 'artists')
  const showPlatformTracksBlock =
    hasActiveQuery &&
    (entityFilter === 'all' || entityFilter === 'tracks')
  const showExternalBlock =
    hasActiveQuery &&
    (entityFilter === 'all' || entityFilter === 'external')
  const hasExternalResults =
    ytResults.length > 0 ||
    bcResults.length > 0 ||
    scResults.length > 0
  const showSearchEmpty =
    hasActiveQuery &&
    tracks !== 'idle' &&
    tracks !== null &&
    Array.isArray(tracks) &&
    ((entityFilter === 'all' &&
      tracks.length === 0 &&
      !hasExternalResults &&
      catalogArtists.length === 0) ||
      (entityFilter === 'tracks' && tracks.length === 0) ||
      (entityFilter === 'artists' && catalogArtists.length === 0) ||
      (entityFilter === 'external' && !hasExternalResults))

  useEffect(() => {
    if (!query.trim()) {
      setEntityFilter('all')
    }
  }, [query])

  return (
    <section id="view-search" className="view active rd-search">
      <div className="search-sticky rd-search-sticky">
        <m.div
          className="search-bar rd-search-bar"
          animate={
            inputFocused
              ? {
                  boxShadow:
                    '0 0 0 2px color-mix(in srgb, var(--accent) 42%, transparent)',
                }
              : { boxShadow: '0 2px 12px rgba(0,0,0,0.06)' }
          }
          transition={SPRING_GENTLE}
        >
        <span className="search-icon"><Icon name="search" size={16} /></span>
        <input
          ref={inputRef}
          id="search-input"
          type="search"
          enterKeyHint="search"
          placeholder={t('search.placeholder')}
          autoComplete="off"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setInputFocused(true)}
          onBlur={() => setInputFocused(false)}
        />
        {query && (
          <button type="button" className="icon-btn" onClick={clearSearch}><Icon name="x" size={16} /></button>
        )}
        </m.div>
      </div>

      {chipsVisible && (
        <div
          className="rd-search-chips"
          role="tablist"
          aria-label={t('redesign.library.searchFiltersAria')}
        >
          {ENTITY_FILTERS.map((f) => (
            <MotionPress
              key={f.id}
              variant="subtle"
              haptic="selection"
              role="tab"
              aria-selected={entityFilter === f.id}
              className="rd-search-chip"
              data-active={entityFilter === f.id ? 'true' : 'false'}
              onClick={() => setEntityFilter(f.id)}
            >
              <Icon name={f.icon} size={14} />
              <span>{t(f.labelKey)}</span>
            </MotionPress>
          ))}
        </div>
      )}

      {tracks === 'idle' && history.length === 0 && (
        <div className="search-idle-hint">
          <Icon name="search" size={32} />
          <p>{t('search.hint')}</p>
        </div>
      )}

      {tracks === 'idle' && history.length > 0 && (
        <div className="search-history">
          <p className="search-section-label">
            {t('search.recent')}
          </p>
          {history.map((h) => (
            <div key={h} className="search-history-item" onClick={() => setQuery(h)}>
              <Icon name="search" size={14} />
              <span>{h}</span>
              <button
                className="icon-btn"
                onClick={(e) => { e.stopPropagation(); removeFromHistory(h) }}
              >
                <Icon name="x" size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {tracks === null && hasActiveQuery && (
        <m.div
          className="search-section rd-search-section"
          variants={VARIANTS_FADE_UP}
          initial="hidden"
          animate="visible"
          transition={TWEEN_FAST}
        >
          <p className="search-section-label">
            {t('search.onPlatform')}
          </p>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="track-card-skeleton shimmer" />
          ))}
        </m.div>
      )}

      {Array.isArray(tracks) && showArtistsBlock && (
        <m.div
          className="search-section rd-search-section"
          variants={VARIANTS_FADE_UP}
          initial="hidden"
          animate="visible"
          transition={{ ...TWEEN_FAST, delay: 0.02 }}
        >
            <p className="search-section-label">
              {t('search.artists')}
            </p>
            {catalogArtists.length > 0 ? (
              catalogArtists.map((a) => (
                <div
                  key={`catalog-artist-${a.id}`}
                  className="track-card search-catalog-artist"
                  role="button"
                  tabIndex={0}
                  aria-label={t('search.catalogArtistRowAria', {
                    name: a.name,
                  })}
                  onClick={() => {
                    onOpenArtist?.(a.id)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onOpenArtist?.(a.id)
                    }
                  }}
                >
                  <CoverImage coverKey={a.image_key} />
                  <div className="track-card-info">
                    <div className="track-card-title-row">
                      <p className="track-card-title">{a.name}</p>
                    </div>
                    <p className="track-card-artist">
                      {t('search.catalogArtistBadge')}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <p className="search-catalog-empty">
                {t('search.artistsEmpty')}
              </p>
            )}
        </m.div>
      )}

      {Array.isArray(tracks) && showPlatformTracksBlock && (
        <m.div
          className="search-section rd-search-section"
          variants={VARIANTS_FADE_UP}
          initial="hidden"
          animate="visible"
          transition={{ ...TWEEN_FAST, delay: 0.04 }}
        >
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
        </m.div>
      )}

      {(tracks === null || Array.isArray(tracks)) && showExternalBlock && (
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
                    <TrackCard
                      key={r.video_id}
                      track={imported}
                    />
                  )
                }
                return (
                  <div
                    key={r.video_id}
                    className="track-card sc-result"
                    onClick={() => handlePlayYT(r)}
                  >
                    <CoverImage
                      coverKey={null}
                      externalUrl={r.thumbnail_url}
                    />
                    <div className="track-card-info">
                      <div className="track-card-title-row">
                        <p className="track-card-title">{r.title}</p>
                        <span className="track-badge track-badge-yt">
                          YT
                        </span>
                      </div>
                      <p className="track-card-artist">
                        {r.artist ?? 'тАФ'}
                      </p>
                      <p className="track-card-meta">
                        {r.duration_seconds != null && (
                          <span className="sc-duration">
                            {Math.floor(
                              r.duration_seconds / 60,
                            )}:{String(
                              r.duration_seconds % 60,
                            ).padStart(2, '0')}
                          </span>
                        )}
                      </p>
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
                        onClick={(e) => handleLikeYT(e, r)}
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
                    onClick={() => handlePlayBC(r)}
                  >
                    <CoverImage
                      coverKey={null}
                      externalUrl={r.artwork_url}
                    />
                    <div className="track-card-info">
                      <div className="track-card-title-row">
                        <p className="track-card-title">{r.title}</p>
                        <span className="track-badge track-badge-bc">
                          BC
                        </span>
                      </div>
                      <p className="track-card-artist">
                        {r.artist ?? 'тАФ'}
                      </p>
                      <p className="track-card-meta">
                        {r.duration_seconds != null && (
                          <span className="sc-duration">
                            {Math.floor(
                              r.duration_seconds / 60,
                            )}:{String(
                              r.duration_seconds % 60,
                            ).padStart(2, '0')}
                          </span>
                        )}
                      </p>
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
                        onClick={(e) => handleLikeBC(e, r)}
                        disabled={importingBc === r.track_url}
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
                    onClick={() => handlePlaySC(r)}
                  >
                    <CoverImage coverKey={null} externalUrl={r.artwork_url} />
                    <div className="track-card-info">
                      <div className="track-card-title-row">
                        <p className="track-card-title">{r.title}</p>
                        <span className="track-badge track-badge-sc">SC</span>
                      </div>
                      <p className="track-card-artist">{r.artist ?? 'тАФ'}</p>
                      <p className="track-card-meta">
                        {r.duration_seconds != null && (
                          <span className="sc-duration">
                            {Math.floor(r.duration_seconds / 60)}:{String(r.duration_seconds % 60).padStart(2, '0')}
                          </span>
                        )}
                      </p>
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
                    <div className="track-card-actions" onClick={(e) => e.stopPropagation()}>
                      <button
                        className="track-card-like"
                        title={t('search.addAndLike')}
                        onClick={(e) => handleLikeSC(e, r)}
                        disabled={importing === r.sc_url}
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

      {showSearchEmpty && (
        <p className="empty-hint">
          {t('search.notFound')}
        </p>
      )}
    </section>
  )
}
