import type { ReactNode } from 'react'
import { TrackCard } from '@/components/TrackCard/TrackCard'
import type { Track } from '@/types/api'

interface Props {
  tracks: Track[] | null
  emptyMessage?: string
  emptyCta?: {
    label: string
    onClick: () => void
  }
  renderExtra?: (track: Track) => ReactNode
}

export function TrackList({
  tracks,
  emptyMessage = 'Ничего не найдено',
  emptyCta,
  renderExtra,
}: Props) {
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
        <div className="empty-state-block">
          <p className="empty-hint">{emptyMessage}</p>
          {emptyCta && (
            <button
              type="button"
              className="empty-cta"
              onClick={emptyCta.onClick}
            >
              {emptyCta.label}
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="track-list">
      {tracks.map((t) => (
        <div key={t.id} className="track-list-item">
          <TrackCard track={t} />
          {renderExtra?.(t)}
        </div>
      ))}
    </div>
  )
}
