import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { TrackCard } from '@/components/TrackCard/TrackCard'
import { SwipeRow } from '@/components/ui/SwipeRow'
import { useToast } from '@/components/ui/Toast'
import { useLikes } from '@/store/LikesContext'
import { usePlayerActions } from '@/store/PlayerContext'
import type { Track } from '@/types/api'

interface Props {
  tracks: Track[] | null
  flavor?: 'default' | 'liked'
  emptyMessage?: string
  emptyCta?: {
    label: string
    onClick: () => void
  }
  renderExtra?: (track: Track) => ReactNode
}

export function TrackList({
  tracks,
  flavor = 'default',
  emptyMessage = 'Ничего не найдено',
  emptyCta,
  renderExtra,
}: Props) {
  const { t } = useTranslation()
  const { isLiked, toggleLike } = useLikes()
  const { addToQueue } = usePlayerActions()
  const toast = useToast()

  if (tracks === null) {
    return (
      <div className="track-list re-tl-root">
        <div className="loader" />
      </div>
    )
  }

  if (tracks.length === 0) {
    return (
      <div className="track-list re-tl-root">
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
    <div className="track-list re-tl-root">
      {tracks.map((tr) => {
        const liked = isLiked(tr.id)
        return (
          <div key={tr.id} className="track-list-item re-tl-item">
            <SwipeRow
              leftAction={{
                icon: liked ? 'heart' : 'heart-outline',
                label:
                  flavor === 'liked'
                    ? t(
                        'redesign.tracks.swipeUnlike',
                        'Unlike',
                      )
                    : t(
                        'redesign.tracks.swipeLike',
                        'Like',
                      ),
                onTrigger: () => {
                  void toggleLike(tr.id)
                },
              }}
              rightAction={{
                icon: 'queue',
                label: t(
                  'redesign.tracks.addQueue',
                  'Queue',
                ),
                onTrigger: () => {
                  addToQueue(tr)
                  toast.success(
                    t(
                      'redesign.tracks.longPressQueued',
                      'Added to queue',
                    ),
                  )
                },
              }}
            >
              <TrackCard track={tr} />
            </SwipeRow>
            {renderExtra?.(tr)}
          </div>
        )
      })}
    </div>
  )
}
