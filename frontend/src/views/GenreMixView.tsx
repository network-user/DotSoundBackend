import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { api } from '@/lib/api'
import { usePlayerActions } from '@/store/PlayerContext'
import type { Track } from '@/types/api'

export function GenreMixView() {
  const { genre } = useParams<{ genre: string }>()
  const navigate = useNavigate()
  const { playTrack } = usePlayerActions()

  const [tracks, setTracks] = useState<Track[] | null>(null)
  const [title, setTitle] = useState<string>(
    genre
      ? 'Mix: ' + genre.charAt(0).toUpperCase() + genre.slice(1)
      : 'Жанровый микс',
  )

  useEffect(() => {
    if (!genre) return
    api
      .getGenreMixes()
      .then((data) => {
        const mix = data.mixes.find(
          (m) =>
            m.genre.toLowerCase() === genre.toLowerCase(),
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
            <span className="hint">
              {tracks.length} треков
            </span>
          )}
        </div>
        {tracks && tracks.length > 0 && (
          <button
            className="icon-btn"
            onClick={handlePlayAll}
            aria-label="Слушать всё"
          >
            <Icon name="play" size={20} />
          </button>
        )}
      </div>

      <TrackList
        tracks={tracks}
        emptyMessage="В этом миксе пока нет треков"
      />
    </section>
  )
}
