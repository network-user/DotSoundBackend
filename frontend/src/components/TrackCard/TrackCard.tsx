import type { MouseEvent } from 'react'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { Icon } from '@/components/Icon/Icon'
import { useLikes } from '@/store/LikesContext'
import { usePlayer } from '@/store/PlayerContext'
import { getInternalUserId } from '@/lib/telegram'
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
  const internalId = getInternalUserId()
  const isOwner = internalId !== null && track.uploaded_by_id === internalId

  const handleLike = async (e: MouseEvent) => {
    e.stopPropagation()
    await toggleLike(track.id)
  }

  const handleDelete = async (e: MouseEvent) => {
    e.stopPropagation()
    if (!internalId) return
    if (!confirm('Удалить трек?')) return
    try {
      await api.deleteTrack(track.id)
      onDeleted?.(track.id)
    } catch { }
  }

  const handleToggleVisibility = async (e: MouseEvent) => {
    e.stopPropagation()
    if (!internalId) return
    try {
      const updated = await api.updateTrack(
        track.id,
        { is_public: !track.is_public },
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
        <div className="track-card-title-row">
          <p className="track-card-title">{track.title}</p>
          {!track.is_public && (
            <span className="track-badge track-badge-private"><Icon name="lock" size={12} /></span>
          )}
          {track.source === 'soundcloud' && (
            <span className="track-badge track-badge-sc">SC</span>
          )}
          {track.source === 'telegram' && (
            <span className="track-badge track-badge-tg">TG</span>
          )}
        </div>
        <p className="track-card-artist">{track.artist ?? 'Неизвестный исполнитель'}</p>
        <p className="track-card-meta">
          ▶ {track.play_count}
          {track.duration_seconds ? ` · ${fmtDuration(track.duration_seconds)}` : ''}
        </p>
        {(track.source_url || track.sc_url) && (
          <span className="track-source">
            источник:{' '}
            <a
              href={track.source_url || track.sc_url || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="track-source-link"
              onClick={(e) => e.stopPropagation()}
            >
              {track.source_name || track.source}
            </a>
          </span>
        )}
        {!track.source_url && !track.sc_url && track.source === 'telegram' && (
          <span className="track-source">источник: Telegram</span>
        )}
      </div>
      <div className="track-card-actions" onClick={(e) => e.stopPropagation()}>
        <button className="track-card-like" title="Лайк" onClick={handleLike}>
          <Icon name={liked ? 'heart' : 'heart-outline'} size={18} />
        </button>
        {isOwner && (
          <>
            <button
              className="track-card-visibility"
              title={track.is_public ? 'Сделать приватным' : 'Сделать публичным'}
              onClick={handleToggleVisibility}
            >
              <Icon name={track.is_public ? 'eye' : 'lock'} size={16} />
            </button>
            <button
              className="track-card-delete"
              title="Удалить трек"
              onClick={handleDelete}
            >
              <Icon name="trash" size={16} />
            </button>
          </>
        )}
      </div>
    </div>
  )
}
