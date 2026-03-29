import type { MouseEvent } from 'react'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { useLikes } from '@/store/LikesContext'
import { usePlayer } from '@/store/PlayerContext'
import { userId } from '@/lib/telegram'
import { api } from '@/lib/api'
import type { Track } from '@/types/api'

interface Props {
  track: Track
  onDeleted?: (trackId: number) => void
  onVisibilityChanged?: (track: Track) => void
}

function fmtDuration(sec: number | null): string {
  if (!sec) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

export function TrackCard({ track, onDeleted, onVisibilityChanged }: Props) {
  const { isLiked, toggleLike } = useLikes()
  const { track: currentTrack, playTrack } = usePlayer()

  const playing = currentTrack?.id === track.id
  const liked = isLiked(track.id)
  const isOwner = userId !== null && track.uploaded_by_id === userId

  const handleLike = async (e: MouseEvent) => {
    e.stopPropagation()
    await toggleLike(track.id)
  }

  const handleDelete = async (e: MouseEvent) => {
    e.stopPropagation()
    if (!userId) return
    if (!confirm('Удалить трек?')) return
    try {
      await api.deleteTrack(track.id, userId)
      onDeleted?.(track.id)
    } catch { }
  }

  const handleToggleVisibility = async (e: MouseEvent) => {
    e.stopPropagation()
    if (!userId) return
    try {
      const updated = await api.updateTrack(
        track.id,
        { is_public: !track.is_public },
        userId,
      )
      onVisibilityChanged?.(updated)
    } catch { }
  }

  return (
    <div
      className={`track-card${playing ? ' playing' : ''}`}
      data-id={track.id}
      onClick={() => playTrack(track)}
    >
      <CoverImage coverKey={track.cover_key} />
      <div className="track-card-info">
        <p className="track-card-title">
          {track.title}
          {!track.is_public && (
            <span className="track-badge track-badge-private">🔒</span>
          )}
          {track.source === 'soundcloud' && (
            <span className="track-badge track-badge-sc">SC</span>
          )}
        </p>
        <p className="track-card-artist">{track.artist ?? 'Неизвестный исполнитель'}</p>
        <p className="track-card-meta">
          ▶ {track.play_count}
          {track.duration_seconds ? ` · ${fmtDuration(track.duration_seconds)}` : ''}
        </p>
      </div>
      <div className="track-card-actions" onClick={(e) => e.stopPropagation()}>
        <button className="track-card-like" title="Лайк" onClick={handleLike}>
          {liked ? '❤️' : '🤍'}
        </button>
        {isOwner && (
          <>
            <button
              className="track-card-visibility"
              title={track.is_public ? 'Сделать приватным' : 'Сделать публичным'}
              onClick={handleToggleVisibility}
            >
              {track.is_public ? '👁' : '🔒'}
            </button>
            <button
              className="track-card-delete"
              title="Удалить трек"
              onClick={handleDelete}
            >
              🗑
            </button>
          </>
        )}
      </div>
    </div>
  )
}
