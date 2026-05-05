import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { usePlayerActions } from '@/store/PlayerContext'
import type { Track } from '@/types/api'

export function GenreMixView() {
  const { genre } = useParams<{ genre: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const { playTrack } = usePlayerActions()

  const [tracks, setTracks] = useState<Track[] | null>(null)
  const [title, setTitle] = useState<string>(
    genre
      ? `Mix: ${genre.charAt(0).toUpperCase()}${genre.slice(1)}`
      : 'Жанровый микс',
  )

  useEffect(() => {
    if (!genre) return
    api
      .getGenreMixes()
      .then((data) => {
        const mix = data.mixes.find(
          (m) => m.genre.toLowerCase() === genre.toLowerCase(),
        )
        if (mix) {
          setTracks(mix.tracks)
          setTitle(mix.title)
        } else {
          setTracks([])
        }
      })
      .catch(() => setTracks([]))
  }, [genre])

  const handlePlayAll = useCallback(async () => {
    if (!tracks || !tracks.length) return
    await playTrack(tracks[0])
  }, [tracks, playTrack])

  const handleShare = useCallback(async () => {
    const url = `${window.location.origin}${import.meta.env.BASE_URL}genre-mix/${encodeURIComponent(
      genre || '',
    )}`
    try {
      if (navigator.share) {
        await navigator.share({ title, url })
        return
      }
      await navigator.clipboard.writeText(url)
      toast.success('Ссылка скопирована')
    } catch {
      toast.error('Не удалось поделиться')
    }
  }, [genre, title, toast])

  return (
    <section className="view active">
      <div className="view-header">
        <button
          className="icon-btn"
          onClick={() => navigate(-1)}
          aria-label="Назад"
        >
          <Icon
            name="chevron"
            size={20}
            className="back-chevron"
          />
        </button>
        <div style={{ flex: 1 }}>
          <h2>{title}</h2>
          {tracks !== null && (
            <span className="hint">{tracks.length} треков</span>
          )}
        </div>
        {tracks && tracks.length > 0 && (
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="icon-btn"
              onClick={() => {
                void handleShare()
              }}
              aria-label="Поделиться"
            >
              <Icon name="share" size={18} />
            </button>
            <button
              className="icon-btn"
              onClick={handlePlayAll}
              aria-label="Слушать всё"
            >
              <Icon name="play" size={20} />
            </button>
          </div>
        )}
      </div>

      <TrackList
        tracks={tracks}
        emptyMessage="В этом миксе пока нет треков"
      />
    </section>
  )
}
