import { useEffect, useRef, useState } from 'react'
import { TrackList } from '@/components/TrackList/TrackList'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { api } from '@/lib/api'
import { userId } from '@/lib/telegram'
import { usePlayer } from '@/store/PlayerContext'
import { useDebounce } from '@/hooks/useDebounce'
import type { SCSearchResult, Track } from '@/types/api'

interface Props {
  active: boolean
}

export function SearchView({ active }: Props) {
  const { playTrack } = usePlayer()
  const [query, setQuery] = useState('')
  const [tracks, setTracks] = useState<Track[] | null | 'idle'>('idle')
  const [scResults, setSCResults] = useState<SCSearchResult[]>([])
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
      api.getTracks({ q: debouncedQuery, size: 20 }).catch(() => ({ items: [] as Track[], total: 0, page: 1, size: 20 })),
      api.searchSoundCloud(debouncedQuery, 10).catch(() => [] as SCSearchResult[]),
    ]).then(([internal, sc]) => {
      setTracks(internal.items)
      setSCResults(sc)
    })
  }, [debouncedQuery])

  const clearSearch = () => {
    setQuery('')
    setTracks('idle')
    setSCResults([])
    inputRef.current?.focus()
  }

  const handlePlaySC = async (result: SCSearchResult) => {
    if (importing === result.sc_url) return
    setImporting(result.sc_url)
    try {
      const track = await api.importSCTrack(
        result.sc_url,
        userId ?? undefined,
        true,
      )
      await playTrack(track)
    } catch { } finally {
      setImporting(null)
    }
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
              {scResults.map((r) => (
                <div
                  key={r.sc_id}
                  className="track-card sc-result"
                  onClick={() => handlePlaySC(r)}
                >
                  <CoverImage coverKey={null} externalUrl={r.artwork_url} />
                  <div className="track-card-info">
                    <p className="track-card-title">
                      {r.title}
                      <span className="track-badge track-badge-sc">SC</span>
                    </p>
                    <p className="track-card-artist">{r.artist ?? '—'}</p>
                    {r.duration_seconds && (
                      <p className="track-card-meta">
                        {Math.floor(r.duration_seconds / 60)}:{String(r.duration_seconds % 60).padStart(2, '0')}
                      </p>
                    )}
                  </div>
                  <span className="sc-play-hint">
                    {importing === r.sc_url ? '…' : '▶'}
                  </span>
                </div>
              ))}
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
