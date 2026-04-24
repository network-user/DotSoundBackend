import { useEffect, useRef, useState } from 'react'
import { TrackList } from '@/components/TrackList/TrackList'
import { TrackCard } from '@/components/TrackCard/TrackCard'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { api } from '@/lib/api'
import { usePlayer } from '@/store/PlayerContext'
import { useLikes } from '@/store/LikesContext'
import { useDebounce } from '@/hooks/useDebounce'
import { Icon } from '@/components/Icon/Icon'
import type {
  SCSearchResult,
  SearchSuggestItem,
  Track,
} from '@/types/api'

type SearchViewProps = {
  onOpenArtist?: (id: number) => void
}

export function SearchView({ onOpenArtist }: SearchViewProps) {
  const { playTrack } = usePlayer()
  const { toggleLike } = useLikes()
  const [query, setQuery] = useState('')
  const [tracks, setTracks] = useState<Track[] | null | 'idle'>('idle')
  const [scResults, setSCResults] = useState<SCSearchResult[]>([])
  const [importedSC, setImportedSC] = useState<Record<string, Track>>({})
  const [importing, setImporting] = useState<string | null>(null)
  const [suggest, setSuggest] = useState<SearchSuggestItem[]>([])
  const debouncedQuery = useDebounce(query, 350)
  const inputRef = useRef<HTMLInputElement>(null)

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
      setSuggest([])
      return
    }
    setTracks(null)
    setSCResults([])
    saveToHistory(debouncedQuery.trim())
    let cancelled = false
    Promise.all([
      api.getTracks({ q: debouncedQuery, size: 20 }).catch(() => ({
        items: [] as Track[],
        total: 0,
        page: 1,
        size: 20,
      })),
      api.searchSoundCloud(debouncedQuery, 10).catch(() => [] as SCSearchResult[]),
      api.searchSuggest(debouncedQuery, 8).catch(() => ({ items: [] })),
    ]).then(([internal, sc, sug]) => {
      if (cancelled) return
      setTracks(internal.items)
      setSCResults(sc)
      setSuggest(sug.items)
    })
    return () => { cancelled = true }
  }, [debouncedQuery])

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

  const handleLikeSC = async (e: React.MouseEvent, result: SCSearchResult) => {
    e.stopPropagation()
    const track = await ensureImported(result)
    if (track) await toggleLike(track.id)
  }

  const clearSearch = () => {
    setQuery('')
    setTracks('idle')
    setSCResults([])
    setSuggest([])
    inputRef.current?.focus()
  }

  const onPickSuggest = async (item: SearchSuggestItem) => {
    if (item.kind === 'track') {
      const t = await api.getTrack(item.id)
      await playTrack(t)
    } else if (item.kind === 'artist' && onOpenArtist) {
      onOpenArtist(item.id)
    }
  }

  return (
    <section id="view-search" className="view active">
      <div className="search-sticky">
        <div className="search-bar">
        <span className="search-icon"><Icon name="search" size={16} /></span>
        <input
          ref={inputRef}
          id="search-input"
          type="text"
          placeholder="Трек или исполнитель…"
          autoComplete="off"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {query && (
          <button className="icon-btn" onClick={clearSearch}><Icon name="x" size={16} /></button>
        )}
        </div>
        {suggest.length > 0 && query.trim() && (
          <ul className="search-suggest" role="listbox" aria-label="Подсказки">
            {suggest.map((s) => (
              <li key={`${s.kind}-${s.id}`} role="option">
                <button
                  type="button"
                  className="search-suggest-row"
                  onClick={() => { void onPickSuggest(s) }}
                >
                  <span className="search-suggest-kind">
                    {s.kind === 'track' ? 'Трек' : 'Артист'}
                  </span>
                  <span className="search-suggest-line">
                    {s.kind === 'track'
                      ? (s.title ?? '—') + (s.name ? ` — ${s.name}` : '')
                      : (s.name ?? '—')}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {tracks === 'idle' && history.length === 0 && (
        <div className="search-idle-hint">
          <Icon name="search" size={32} />
          <p>Начните вводить название трека или исполнителя</p>
        </div>
      )}

      {tracks === 'idle' && history.length > 0 && (
        <div className="search-history">
          <p className="search-section-label">Недавние</p>
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

      {tracks === null && (
        <div className="search-section">
          <p className="search-section-label">На платформе</p>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="track-card-skeleton shimmer" />
          ))}
        </div>
      )}

      {Array.isArray(tracks) && (
        <>
          {tracks.length > 0 && (
            <div className="search-section">
              <p className="search-section-label">На платформе</p>
              <TrackList tracks={tracks} emptyMessage="" />
            </div>
          )}

          {scResults.length > 0 && (
            <div className="search-section">
              <p className="search-section-label">
                SoundCloud · внешний источник
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
                      <p className="track-card-artist">{r.artist ?? '—'}</p>
                      <p className="track-card-meta">
                        {r.duration_seconds != null && (
                          <span className="sc-duration">
                            {Math.floor(r.duration_seconds / 60)}:{String(r.duration_seconds % 60).padStart(2, '0')}
                          </span>
                        )}
                      </p>
                      <span className="track-source">
                        внешний источник:{' '}
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
                        после добавления трек будет доступен как
                        внешний поток стороннего сервиса
                      </span>
                    </div>
                    <div className="track-card-actions" onClick={(e) => e.stopPropagation()}>
                      <button
                        className="track-card-like"
                        title="Добавить и лайкнуть"
                        onClick={(e) => handleLikeSC(e, r)}
                        disabled={importing === r.sc_url}
                      >
                        <Icon name="heart-outline" size={18} />
                      </button>
                      <span className="sc-play-hint">
                        {importing === r.sc_url ? '...' : 'Добавить и слушать'}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {tracks.length === 0 && scResults.length === 0 && (
            <p className="empty-hint">Ничего не найдено</p>
          )}
        </>
      )}
    </section>
  )
}
