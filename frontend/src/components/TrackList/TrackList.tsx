import { useLayoutEffect, useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useTranslation } from 'react-i18next'
import { TrackCard } from '@/components/TrackCard/TrackCard'
import { SwipeRow } from '@/components/ui/SwipeRow'
import { showIsland } from '@/lib/island'
import { MotionPress } from '@/components/ui/MotionPress'
import { useLikes } from '@/store/LikesContext'
import { usePlayerActions } from '@/store/PlayerContext'
import type { Track } from '@/types/api'

const ITEM_HEIGHT_ESTIMATE = 72
const OVERSCAN = 5

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
  const listRef = useRef<HTMLDivElement>(null)
  const [scrollMargin, setScrollMargin] = useState(0)

  const count = tracks?.length ?? 0

  useLayoutEffect(() => {
    if (!count) return
    const mainEl = document.getElementById('main')
    const listEl = listRef.current
    if (!mainEl || !listEl) return
    const mainRect = mainEl.getBoundingClientRect()
    const listRect = listEl.getBoundingClientRect()
    setScrollMargin(
      listRect.top - mainRect.top + mainEl.scrollTop,
    )
  }, [count])

  const virtualizer = useVirtualizer({
    count,
    getScrollElement: () => document.getElementById('main'),
    estimateSize: () => ITEM_HEIGHT_ESTIMATE,
    overscan: OVERSCAN,
    scrollMargin,
  })

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

  const virtualItems = virtualizer.getVirtualItems()

  return (
    <div
      ref={listRef}
      className="track-list re-tl-root"
      style={{
        height: virtualizer.getTotalSize(),
        position: 'relative',
      }}
    >
      {virtualItems.map((virtualRow) => {
        const tr = tracks[virtualRow.index]!
        const liked = isLiked(tr.id)
        return (
          <div
            key={virtualRow.key}
            data-index={virtualRow.index}
            ref={virtualizer.measureElement}
            className="track-list-item re-tl-item"
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              transform: `translateY(${
                virtualRow.start - scrollMargin
              }px)`,
            }}
          >
            <SwipeRow
              leftAction={{
                icon: liked ? 'heart' : 'heart-outline',
                label:
                  flavor === 'liked'
                    ? t('redesign.tracks.swipeUnlike', 'Unlike')
                    : t('redesign.tracks.swipeLike', 'Like'),
                onTrigger: () => {
                  void toggleLike(tr.id, tr)
                },
              }}
              rightAction={{
                icon: 'queue',
                label: t('redesign.tracks.addQueue', 'Queue'),
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
