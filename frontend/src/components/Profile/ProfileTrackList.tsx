import { TrackCard } from '@/components/TrackCard/TrackCard'
import type { Track } from '@/types/api'

interface Props {
  tracks: Track[]
  onPlay: (track: Track) => void
  onToggleVisibility: (track: Track) => void
  onDelete: (track: Track) => void
}

export function ProfileTrackList({
  tracks,
  onToggleVisibility,
  onDelete,
}: Props) {
  if (tracks.length === 0) return null

  const handleDeleted = (trackId: number) => {
    const track = tracks.find((t) => t.id === trackId)
    if (track) onDelete(track)
  }

  const handleVisibilityChanged = (updated: Track) => {
    onToggleVisibility(updated)
  }

  return (
    <div className="my-tracks-section">
      <div className="section-header">
        <span className="section-title">
          Мои треки ({tracks.length})
        </span>
      </div>
      <div className="track-list">
        {tracks.map((track) => (
          <TrackCard
            key={track.id}
            track={track}
            onDeleted={handleDeleted}
            onVisibilityChanged={handleVisibilityChanged}
          />
        ))}
      </div>
    </div>
  )
}
