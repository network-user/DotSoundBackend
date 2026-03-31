import type { Track } from '@/types/api'

interface Props {
  tracks: Track[]
  onPlay: (track: Track) => void
  onToggleVisibility: (track: Track) => void
  onDelete: (track: Track) => void
}

export function ProfileTrackList({ tracks, onPlay, onToggleVisibility, onDelete }: Props) {
  if (tracks.length === 0) return null

  return (
    <div className="my-tracks-section">
      <p className="my-tracks-label">Мои треки</p>
      {tracks.map((track) => (
        <div key={track.id} className="my-track-row" onClick={() => onPlay(track)}>
          <div className="my-track-info">
            <span className="my-track-title">{track.title}</span>
            {track.source === 'soundcloud' && (
              <span className="track-badge track-badge-sc">SC</span>
            )}
            {!track.is_public && (
              <span className="track-badge track-badge-private">🔒</span>
            )}
          </div>
          <div className="my-track-actions" onClick={(e) => e.stopPropagation()}>
            <button
              className="icon-btn"
              title={track.is_public ? 'Сделать приватным' : 'Сделать публичным'}
              onClick={() => onToggleVisibility(track)}
            >
              {track.is_public ? '👁' : '🔒'}
            </button>
            <button
              className="icon-btn"
              title="Удалить"
              onClick={() => onDelete(track)}
            >
              🗑
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
