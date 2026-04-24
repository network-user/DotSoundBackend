import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent,
} from 'react'
import { Icon } from '@/components/Icon/Icon'
import { useLikes } from '@/store/LikesContext'
import { usePlayer } from '@/store/PlayerContext'
import { haptic } from '@/lib/telegram'
import { useRipple } from '@/components/ui/Ripple'

const PLATFORM_LABELS: Record<string, string> = {
  youtube: 'YouTube',
  bandcamp: 'Bandcamp',
  vk: 'VK Музыка',
  yandex: 'Яндекс Музыка',
}

function fmt(sec: number) {
  if (!sec || isNaN(sec)) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
    .toString()
    .padStart(2, '0')
  return `${m}:${s}`
}

export function PlayerBar() {
  const {
    track,
    isPlaying,
    currentTime,
    duration,
    togglePlay,
    seek,
    playNext,
    playPrev,
    openCard,
    openEq,
    openQueue,
    stop,
    repeatMode,
    shuffleOn,
    hlsError,
    toggleRepeat,
    toggleShuffle,
    clearHlsError,
  } = usePlayer()
  const { isLiked, toggleLike } = useLikes()
  const [likeBurst, setLikeBurst] =
    useState(false)
  const [overflowOpen, setOverflowOpen] =
    useState(false)
  const overflowRef = useRef<HTMLDivElement>(null)
  const playRef = useRef<HTMLButtonElement>(null)
  const prevRef = useRef<HTMLButtonElement>(null)
  const nextRef = useRef<HTMLButtonElement>(null)
  const likeRef = useRef<HTMLButtonElement>(null)
  useRipple(playRef)
  useRipple(prevRef)
  useRipple(nextRef)
  useRipple(likeRef)

  useEffect(() => {
    if (!overflowOpen) return
    const onDocClick = (e: globalThis.MouseEvent) => {
      if (
        overflowRef.current &&
        !overflowRef.current.contains(
          e.target as Node,
        )
      ) {
        setOverflowOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape')
        setOverflowOpen(false)
    }
    document.addEventListener(
      'pointerdown',
      onDocClick,
    )
    window.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener(
        'pointerdown',
        onDocClick,
      )
      window.removeEventListener('keydown', onKey)
    }
  }, [overflowOpen])

  if (!track) return null

  const pct = duration
    ? (currentTime / duration) * 100
    : 0
  const liked = isLiked(track.id)

  const coverSrc = track.cover_key
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(track.cover_key)}`
    : null

  const handleOpenCard = (e: MouseEvent) => {
    e.stopPropagation()
    openCard()
  }

  const handleLike = async (e: MouseEvent) => {
    e.stopPropagation()
    if (!liked) {
      setLikeBurst(true)
      window.setTimeout(() => setLikeBurst(false), 520)
    }
    haptic(liked ? 'light' : 'medium')
    await toggleLike(track.id)
  }

  const handlePlay = (e: MouseEvent) => {
    e.stopPropagation()
    haptic('light')
    togglePlay()
  }

  const handleNext = (e: MouseEvent) => {
    e.stopPropagation()
    haptic('light')
    playNext()
  }

  const handlePrev = (e: MouseEvent) => {
    e.stopPropagation()
    haptic('light')
    playPrev()
  }

  const seekStyle = {
    '--progress': `${pct}%`,
  } as CSSProperties

  const repeatTitle =
    repeatMode === 'none'
      ? 'Повтор выкл.'
      : repeatMode === 'one'
        ? 'Повтор трека'
        : 'Повтор всех'

  return (
    <div id="player-bar">
      <div id="pb-seek-wrap" className="pb-seek-zone">
        <input
          type="range"
          id="pb-seek"
          min={0}
          max={100}
          step={0.1}
          value={pct}
          style={seekStyle}
          aria-label="Перемотка трека"
          onChange={(e) =>
            seek(Number(e.target.value))
          }
        />
      </div>

      <div id="pb-row" className="pb-row-v2">
        <div
          className="pb-cover-img pb-clickable"
          onClick={handleOpenCard}
        >
          {coverSrc ? (
            <img
              src={coverSrc}
              alt=""
              loading="lazy"
              className="pb-cover-vt"
              style={
                {
                  viewTransitionName: `cover-t-${track.id}`,
                } as CSSProperties
              }
            />
          ) : (
            <Icon name="music" size={18} />
          )}
        </div>

        <div
          id="pb-info"
          className="pb-clickable"
          onClick={handleOpenCard}
        >
          <p className="pb-title">{track.title}</p>
          <p className="pb-artist hint">
            {track.artist ?? '—'}
          </p>
          {track.source_platform &&
            track.source_platform !== 'soundcloud' &&
            track.source_url && (
              <a
                className="pb-source-link"
                href={track.source_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                title={`Слушать на ${PLATFORM_LABELS[track.source_platform] ?? track.source_platform}`}
              >
                <Icon
                  name={`source-${track.source_platform}`}
                  size={12}
                />
                <span>{PLATFORM_LABELS[track.source_platform] ?? track.source_platform}</span>
              </a>
            )}
        </div>

        <div id="pb-controls" className="pb-ctl-v2">
          <button
            ref={prevRef}
            className="ctrl-btn pb-prev"
            onClick={handlePrev}
            aria-label="Предыдущий"
          >
            <Icon name="skip-back" size={18} />
          </button>
          <button
            ref={playRef}
            className="play-btn"
            onClick={handlePlay}
            aria-label={
              isPlaying ? 'Пауза' : 'Воспроизвести'
            }
          >
            <Icon
              name={isPlaying ? 'pause' : 'play'}
              size={16}
            />
          </button>
          <button
            ref={nextRef}
            className="ctrl-btn"
            onClick={handleNext}
            aria-label="Следующий"
          >
            <Icon name="skip-forward" size={18} />
          </button>
          <button
            ref={likeRef}
            className={`icon-btn pb-like${liked ? ' liked' : ''}${
              likeBurst ? ' pb-like-burst' : ''
            }`}
            onClick={handleLike}
            aria-label={
              liked ? 'Убрать лайк' : 'Лайк'
            }
            aria-pressed={liked}
          >
            <Icon
              name={
                liked ? 'heart' : 'heart-outline'
              }
              size={18}
            />
          </button>
          <div
            className="pb-overflow-wrap"
            ref={overflowRef}
          >
            <button
              className="ctrl-btn pb-overflow-btn"
              onClick={(e) => {
                e.stopPropagation()
                setOverflowOpen((v) => !v)
              }}
              aria-label="Дополнительно"
              aria-expanded={overflowOpen}
              aria-haspopup="menu"
            >
              <Icon
                name="more-horizontal"
                size={18}
              />
            </button>
            {overflowOpen && (
              <div
                className="pb-overflow-menu"
                role="menu"
              >
                <button
                  role="menuitem"
                  className="pb-menu-item"
                  onClick={() => {
                    setOverflowOpen(false)
                    openQueue()
                  }}
                >
                  <Icon name="queue" size={16} />
                  Очередь
                </button>
                <button
                  role="menuitem"
                  className="pb-menu-item"
                  onClick={() => {
                    setOverflowOpen(false)
                    openEq()
                  }}
                >
                  <Icon name="eq" size={16} />
                  Эквалайзер
                </button>
                <button
                  role="menuitem"
                  className={`pb-menu-item ${shuffleOn ? 'active' : ''}`}
                  onClick={() => {
                    haptic('light')
                    toggleShuffle()
                    setOverflowOpen(false)
                  }}
                >
                  <Icon name="shuffle" size={16} />
                  Перемешать
                </button>
                <button
                  role="menuitem"
                  className={`pb-menu-item ${repeatMode !== 'none' ? 'active' : ''}`}
                  onClick={() => {
                    haptic('light')
                    toggleRepeat()
                    setOverflowOpen(false)
                  }}
                  title={repeatTitle}
                >
                  <Icon
                    name={
                      repeatMode === 'one'
                        ? 'repeat-one'
                        : 'repeat'
                    }
                    size={16}
                  />
                  {repeatTitle}
                </button>
                <button
                  role="menuitem"
                  className="pb-menu-item pb-menu-item-danger"
                  onClick={() => {
                    setOverflowOpen(false)
                    stop()
                  }}
                >
                  <Icon name="x" size={16} />
                  Остановить
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <div id="pb-time">
        <span>{fmt(currentTime)}</span>
        <span>{fmt(duration)}</span>
      </div>

      {hlsError && (
        <div
          className="pb-error-toast"
          onClick={clearHlsError}
          role="button"
          aria-label="Закрыть ошибку"
        >
          <span>{hlsError}</span>
          <Icon name="x" size={14} />
        </div>
      )}
    </div>
  )
}
