import type { MouseEvent } from 'react'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { useLikes } from '@/store/LikesContext'
import { usePlayer } from '@/store/PlayerContext'
import type { Track } from '@/types/api'

interface Props {
  track: Track
}

export function TrackCard({ track }: Props) {
  const { isLiked, toggleLike } = useLikes()
  const { track: currentTrack, playTrack } = usePlayer()

  const playing = currentTrack?.id === track.id
  const liked = isLiked(track.id)

  const handleLike = async (e: MouseEvent) => {
    e.stopPropagation()
    await toggleLike(track.id)
  }

  return (
    <div
      className={`track-card${playing ? ' playing' : ''}`}
      data-id={track.id}
      onClick={() => playTrack(track)}
    >
      <CoverImage coverKey={track.cover_key} />
      <div className="track-card-info">
        <p className="track-card-title">{track.title}</p>
        <p className="track-card-artist">{track.artist ?? 'Неизвестный исполнитель'}</p>
        <p className="track-card-meta">▶ {track.play_count}</p>
      </div>
      <button className="track-card-like" title="Лайк" onClick={handleLike}>
        {liked ? '❤️' : '🤍'}
      </button>
    </div>
  )
}
