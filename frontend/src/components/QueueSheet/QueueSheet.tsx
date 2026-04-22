import { useRef, useState } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { useExitTransition } from '@/hooks/useExitTransition'
import {
  usePlayerActions,
  usePlayerMeta,
  usePlayerState,
} from '@/store/PlayerContext'
import type { Track } from '@/types/api'

export function QueueSheet() {
  const {
    track,
    isQueueOpen,
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

  const exit = useExitTransition(isQueueOpen)
  const [dragIdx, setDragIdx] = useState<
    number | null
  >(null)
  const dragOverIdx = useRef<number | null>(null)

  if (!exit.mounted) return null

  const onClickItem = (t: Track) => {
    if (t.id === track?.id) {
      togglePlay()
    } else {
      playTrack(t)
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

  return (
    <div
      className={`queue-backdrop${exit.cls}`}
      onClick={(e) => {
        if (e.target === e.currentTarget) closeQueue()
      }}
    >
      <div className={`queue-sheet${exit.cls}`}>
        <div className="queue-handle" />
        <div className="queue-header">
          <span className="queue-title">
            Очередь
          </span>
          <button
            className="icon-btn"
            onClick={closeQueue}
            aria-label="Закрыть"
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className="queue-content">
          {history.length > 0 && (
            <section className="queue-section">
              <div className="queue-section-title">
                Недавно
              </div>
              {history
                .slice(-5)
                .reverse()
                .map((t) => (
                  <QueueRow
                    key={`h-${t.id}`}
                    t={t}
                    onClick={() => onClickItem(t)}
                    muted
                  />
                ))}
            </section>
          )}

          {track && (
            <section className="queue-section">
              <div className="queue-section-title">
                Сейчас играет
              </div>
              <QueueRow
                t={track}
                onClick={togglePlay}
                playing={isPlaying}
                primary
              />
            </section>
          )}

          {queue.length > 0 ? (
            <section className="queue-section">
              <div className="queue-section-title queue-section-title-row">
                <span>Дальше</span>
                <button
                  className="queue-action-btn"
                  onClick={clearQueue}
                >
                  Очистить
                </button>
              </div>
              {queue.map((t, idx) => (
                <div
                  key={`q-${t.id}-${idx}`}
                  className={`queue-row-wrap${dragIdx === idx ? ' dragging' : ''}`}
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
                  <QueueRow
                    t={t}
                    onClick={() => onClickItem(t)}
                    onRemove={() =>
                      removeFromQueue(idx)
                    }
                    grabbable
                  />
                </div>
              ))}
            </section>
          ) : (
            <section className="queue-section queue-empty">
              <div className="queue-empty-text">
                Очередь пуста.
                <br />
                Зажмите трек, чтобы добавить в
                очередь.
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}

function QueueRow({
  t,
  onClick,
  onRemove,
  playing,
  primary,
  muted,
  grabbable,
}: {
  t: Track
  onClick: () => void
  onRemove?: () => void
  playing?: boolean
  primary?: boolean
  muted?: boolean
  grabbable?: boolean
}) {
  const cover = t.cover_key
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(t.cover_key)}`
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
      <button
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
            {t.title}
          </span>
          <span className="queue-row-artist">
            {t.artist || '—'}
          </span>
        </span>
        {primary && playing && (
          <span
            className="queue-eq-bars"
            aria-hidden="true"
          >
            <span />
            <span />
            <span />
          </span>
        )}
      </button>
      {onRemove && (
        <button
          className="icon-btn queue-remove"
          onClick={onRemove}
          aria-label="Убрать из очереди"
        >
          <Icon name="x" size={14} />
        </button>
      )}
    </div>
  )
}
