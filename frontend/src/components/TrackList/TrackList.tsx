import { useTranslation } from 'react-i18next'
import { TrackCard } from '@/components/TrackCard/TrackCard'
import { SwipeRow } from '@/components/ui/SwipeRow'
import { showIsland } from '@/lib/island'
import { MotionPress } from '@/components/ui/MotionPress'
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
  /**
   * Tracks list that should be used as playback context when the
   * user taps an individual card (defaults to `tracks`). Set
   * explicitly when the rendered list is a slice of a larger queue.
   */
  contextTracks?: Track[]
}

export function TrackList({
  tracks,
  flavor = 'default',
  emptyMessage = 'Ничего не найдено',
  emptyCta,
  contextTracks,
}: Props) {
  const { t } = useTranslation()
  const { isLiked, toggleLike } = useLikes()
  const { addToQueue } = usePlayerActions()

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
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="empty-cta"
              onClick={emptyCta.onClick}
            >
              {emptyCta.label}
            </MotionPress>
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
                  void toggleLike(tr.id, tr)
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
                  showIsland({
                    kind: 'toast',
                    title: t(
                      'redesign.tracks.longPressQueued',
                      'Added to queue',
                    ),
                    durationMs: 2000,
                  })
                },
              }}
            >
              <TrackCard
                track={tr}
                contextTracks={contextTracks ?? tracks}
              />
            </SwipeRow>
          </div>
        )
      })}
    </div>
  )
}
