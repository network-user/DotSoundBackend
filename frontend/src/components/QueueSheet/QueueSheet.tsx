import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { useExitTransition } from '@/hooks/useExitTransition'
import {
  usePlayerActions,
  usePlayerMeta,
  usePlayerState,
} from '@/store/PlayerContext'
import type { Track } from '@/types/api'
import { SwipeRow } from '@/components/ui/SwipeRow'
import { BeatPulse } from '@/components/ui/BeatPulse'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { MotionPress } from '@/components/ui/MotionPress'

export type QueuePanelContentProps = {
  inline?: boolean
}

export function QueuePanelContent({
  inline = false,
}: QueuePanelContentProps) {
  const { t } = useTranslation()
  const {
    track,
    queue,
    history,
  } = usePlayerMeta()
  const { isPlaying } = usePlayerState()
  const {
    closeQueue,
    playTrack,
    removeFromQueue,
    clearQueue,
    reorderQueue,
    togglePlay,
  } = usePlayerActions()

  const [dragIdx, setDragIdx] = useState<
    number | null
  >(null)
  const dragOverIdx = useRef<number | null>(null)

  const onClickItem = (tr: Track) => {
    if (tr.id === track?.id) {
      togglePlay()
    } else {
      playTrack(tr)
    }
  }

  const onDragStart = (idx: number) =>
    setDragIdx(idx)
  const onDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault()
    dragOverIdx.current = idx
  }
  const onDragEnd = () => {
    if (
      dragIdx !== null &&
      dragOverIdx.current !== null &&
      dragIdx !== dragOverIdx.current
    ) {
      reorderQueue(dragIdx, dragOverIdx.current)
    }
    setDragIdx(null)
    dragOverIdx.current = null
  }

  const inner = (
    <div
      className={
        inline
          ? 'queue-content queue-content--inline rp-now-queue-embed'
          : 'queue-content'
      }
    >
      {history.length > 0 && (
        <section className="queue-section">
          <div className="queue-section-title">
            {t(
              'redesign.player.queueRecent',
              'Recently played',
            )}
          </div>
          {history
            .slice(-5)
            .reverse()
            .map((tr) => (
              <QueueRow
                key={`h-${tr.id}`}
                track={tr}
                onClick={() => onClickItem(tr)}
                muted
              />
            ))}
        </section>
      )}

      {track && (
        <section className="queue-section">
          <div className="queue-section-title">
            {t(
              'redesign.player.queueNowPlaying',
              'Now playing',
            )}
          </div>
          <QueueRow
            track={track}
            onClick={togglePlay}
            playing={isPlaying}
            primary
          />
        </section>
      )}

      {queue.length > 0 ? (
        <section className="queue-section">
          <div className="queue-section-title queue-section-title-row">
            <span>
              {t(
                'redesign.player.queueUpNext',
                'Up next',
              )}
            </span>
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="queue-action-btn"
              onClick={clearQueue}
            >
              {t('redesign.player.queueClear', 'Clear')}
            </MotionPress>
          </div>
          {queue.map((tr, idx) => (
            <div
              key={`q-${tr.id}-${idx}`}
              className={`queue-row-wrap rp-queue-row${dragIdx === idx ? ' dragging' : ''}`}
              draggable
              onDragStart={() =>
                onDragStart(idx)
              }
              onDragOver={(e) =>
                onDragOver(e, idx)
              }
              onDragEnd={onDragEnd}
              onDrop={onDragEnd}
            >
              <SwipeRow
                rightAction={{
                  icon: 'trash',
                  label: t(
                    'redesign.player.queueDeleteSwipe',
                    'Remove',
                  ),
                  destructive: true,
                  onTrigger: () =>
                    removeFromQueue(idx),
                }}
              >
                <QueueRow
                  track={tr}
                  onClick={() =>
                    onClickItem(tr)
                  }
                  onRemove={() =>
                    removeFromQueue(idx)
                  }
                  grabbable
                />
              </SwipeRow>
            </div>
          ))}
        </section>
      ) : (
        <section className="queue-section queue-empty">
          <div className="queue-empty-text">
            {t('redesign.player.queueEmpty', 'Queue is empty.')}
            <br />
            {t(
              'redesign.player.queueEmptyHint',
              'Long-press a track to add it to the queue.',
            )}
          </div>
        </section>
      )}
    </div>
  )

  if (inline) {
    return inner
  }

  return (
    <>
      <div className="queue-handle" />
      <div className="queue-header">
        <span className="queue-title">
          {t('redesign.player.queueTitle', 'Queue')}
        </span>
        <MotionPress
          variant="ghost"
          haptic="selection"
          className="icon-btn"
          onClick={closeQueue}
          aria-label={t('redesign.player.queueClose', 'Close')}
        >
          <Icon name="x" size={18} />
        </MotionPress>
      </div>
      {inner}
    </>
  )
}

export function QueueSheet() {
  const { isQueueOpen } = usePlayerMeta()
  const { closeQueue } = usePlayerActions()
  const exit = useExitTransition(isQueueOpen)

  if (!exit.mounted) return null

  return (
    <div
      className={`queue-backdrop${exit.cls}`}
      onClick={(e) => {
        if (e.target === e.currentTarget) closeQueue()
      }}
    >
      <div className={`queue-sheet${exit.cls}`}>
        <QueuePanelContent />
      </div>
    </div>
  )
}

function QueueRow({
  track,
  onClick,
  onRemove,
  playing,
  primary,
  muted,
  grabbable,
}: {
  track: Track
  onClick: () => void
  onRemove?: () => void
  playing?: boolean
  primary?: boolean
  muted?: boolean
  grabbable?: boolean
}) {
  const { t } = useTranslation()
  const cover = track.cover_key
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(track.cover_key)}`
    : null

  return (
    <div
      className={`queue-row${primary ? ' primary' : ''}${muted ? ' muted' : ''}`}
    >
      {grabbable && (
        <span
          className="queue-grab"
          aria-hidden="true"
        >
          <Icon name="more-vertical" size={14} />
        </span>
      )}
      <MotionPress
        variant="ghost"
        haptic="selection"
        className="queue-row-main"
        onClick={onClick}
      >
        <span className="queue-cover">
          {cover ? (
            <img src={cover} alt="" />
          ) : (
            <Icon name="music" size={16} />
          )}
        </span>
        <span className="queue-meta">
          <span className="queue-row-title">
            {track.title}
          </span>
          <span className="queue-row-artist">
            {track.artist || '—'}
          </span>
        </span>
        {primary && (
          <span
            className="queue-eq-bars rp-queue-eq"
            aria-hidden="true"
          >
            <BeatPulse bpm={120} active={!!playing}>
              <MorphIcon
                name="play"
                filled={!!playing}
                size={14}
              />
            </BeatPulse>
          </span>
        )}
      </MotionPress>
      {onRemove && (
        <MotionPress
          variant="ghost"
          haptic="selection"
          className="icon-btn queue-remove"
          onClick={onRemove}
          aria-label={t(
            'redesign.player.queueRemoveAria',
            'Remove from queue',
          )}
        >
          <Icon name="x" size={14} />
        </MotionPress>
      )}
    </div>
  )
}
