import { TrackCard } from '@/components/TrackCard/TrackCard'
import type { Track } from '@/types/api'

interface Props {
  tracks: Track[] | null
  emptyMessage?: string
}

export function TrackList({ tracks, emptyMessage = 'Ничего не найдено' }: Props) {
  if (tracks === null) {
    return (
      <div className="track-list">
        <div className="loader" />
      </div>
    )
  }

  if (tracks.length === 0) {
    return (
      <div className="track-list">
        <p className="empty-hint">{emptyMessage}</p>
      </div>
    )
  }

  return (
    <div className="track-list">
      {tracks.map((t) => (
        <TrackCard key={t.id} track={t} />
      ))}
    </div>
  )
}
