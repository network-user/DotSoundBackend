import { useEffect, useRef, useState } from 'react'
import { TrackList } from '@/components/TrackList/TrackList'
import { TrackCard } from '@/components/TrackCard/TrackCard'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { api } from '@/lib/api'
import { usePlayer } from '@/store/PlayerContext'
import { useLikes } from '@/store/LikesContext'
import { useDebounce } from '@/hooks/useDebounce'
import type { SCSearchResult, Track } from '@/types/api'

interface Props {
  active: boolean
}

export function SearchView({ active }: Props) {
  const { playTrack } = usePlayer()
  const { toggleLike } = useLikes()
  const [query, setQuery] = useState('')
  const [tracks, setTracks] = useState<Track[] | null | 'idle'>('idle')
  const [scResults, setSCResults] = useState<SCSearchResult[]>([])
  const [importedSC, setImportedSC] = useState<Record<string, Track>>({})
  const [importing, setImporting] = useState<string | null>(null)
  const debouncedQuery = useDebounce(query, 350)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (active) inputRef.current?.focus()
  }, [active])

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setTracks('idle')
      setSCResults([])
      return
    }
    setTracks(null)
    setSCResults([])
    Promise.all([
      api.getTracks({ q: debouncedQuery, size: 20 }).catch(() => ({
        items: [] as Track[],
        total: 0,
        page: 1,
        size: 20,
      })),
      api.searchSoundCloud(debouncedQuery, 10).catch(() => [] as SCSearchResult[]),
    ]).then(([internal, sc]) => {
      setTracks(internal.items)
      setSCResults(sc)
    })
  }, [debouncedQuery])

  const ensureImported = async (result: SCSearchResult): Promise<Track | null> => {
    if (importedSC[result.sc_url]) return importedSC[result.sc_url]
    if (importing === result.sc_url) return null
    setImporting(result.sc_url)
    try {
      const track = await api.importSCTrack(
        result.sc_url,
        true,
      )
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
    inputRef.current?.focus()
  }

  return (
    <section id="view-search" className={`view${active ? ' active' : ''}`}>
      <div className="search-bar">
        <span className="search-icon">🔍</span>
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
          <button className="icon-btn" onClick={clearSearch}>✕</button>
        )}
      </div>

      {tracks === 'idle' ? (
        <p className="empty-hint">Начните вводить название</p>
      ) : (
        <>
          {Array.isArray(tracks) && tracks.length > 0 && (
            <div className="search-section">
              <p className="search-section-label">На платформе</p>
              <TrackList tracks={tracks} emptyMessage="" />
            </div>
          )}

          {scResults.length > 0 && (
            <div className="search-section">
              <p className="search-section-label">SoundCloud</p>
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
                        источник:{' '}
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
                    </div>
                    <div className="track-card-actions" onClick={(e) => e.stopPropagation()}>
                      <button
                        className="track-card-like"
                        title="Лайк"
                        onClick={(e) => handleLikeSC(e, r)}
                        disabled={importing === r.sc_url}
                      >
                        🤍
                      </button>
                      <span className="sc-play-hint">
                        {importing === r.sc_url ? '…' : '▶'}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {Array.isArray(tracks) && tracks.length === 0 && scResults.length === 0 && (
            <p className="empty-hint">Ничего не найдено</p>
          )}
        </>
      )}
    </section>
  )
}
