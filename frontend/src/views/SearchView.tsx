import { useEffect, useRef, useState } from 'react'
import { TrackList } from '@/components/TrackList/TrackList'
import { api } from '@/lib/api'
import { useDebounce } from '@/hooks/useDebounce'
import type { Track } from '@/types/api'

interface Props {
  active: boolean
}

export function SearchView({ active }: Props) {
  const [query, setQuery] = useState('')
  const [tracks, setTracks] = useState<Track[] | null | 'idle'>('idle')
  const debouncedQuery = useDebounce(query, 350)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (active) inputRef.current?.focus()
  }, [active])

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setTracks('idle')
      return
    }
    setTracks(null)
    api.getTracks({ q: debouncedQuery, size: 30 })
      .then((data) => setTracks(data.items))
      .catch(() => setTracks([]))
  }, [debouncedQuery])

  const clearSearch = () => {
    setQuery('')
    setTracks('idle')
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
        <TrackList tracks={tracks} emptyMessage="Ничего не найдено" />
      )}
    </section>
  )
}
