import { useLikes } from '@/store/LikesContext'
import { usePlayer } from '@/store/PlayerContext'
import { Icon } from '@/components/Icon/Icon'
import type { MouseEvent } from 'react'

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
  } = usePlayer()
  const { isLiked, toggleLike } = useLikes()

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
    await toggleLike(track.id)
  }

  return (
    <div id="player-bar">
      <div id="pb-seek-wrap">
        <input
          type="range"
          id="pb-seek"
          min={0}
          max={100}
          step={0.1}
          value={pct}
          onChange={(e) =>
            seek(Number(e.target.value))
          }
        />
      </div>
      <div id="pb-row">
        <div
          className="pb-cover-img pb-clickable"
          onClick={handleOpenCard}
        >
          {coverSrc ? (
            <img src={coverSrc} alt="" />
          ) : (
            <Icon name="music" size={18} />
          )}
        </div>
        <div
          id="pb-info"
          className="pb-clickable"
          onClick={handleOpenCard}
        >
          <p className="pb-title">
            {track.title}
          </p>
          <p className="pb-artist hint">
            {track.artist ?? '—'}
          </p>
        </div>
        <div id="pb-controls">
          <button
            className={`icon-btn${liked ? ' liked' : ''}`}
            onClick={handleLike}
          >
            <Icon
              name={
                liked ? 'heart' : 'heart-outline'
              }
              size={18}
            />
          </button>
          <button
            className="ctrl-btn"
            onClick={openEq}
          >
            <Icon name="eq" size={18} />
          </button>
          <button
            className="ctrl-btn"
            onClick={playPrev}
          >
            <Icon name="skip-back" size={18} />
          </button>
          <button
            className="play-btn"
            onClick={togglePlay}
          >
            <Icon
              name={isPlaying ? 'pause' : 'play'}
              size={16}
            />
          </button>
          <button
            className="ctrl-btn"
            onClick={playNext}
          >
            <Icon
              name="skip-forward"
              size={18}
            />
          </button>
        </div>
      </div>
      <div id="pb-time">
        <span>{fmt(currentTime)}</span>
        <span>{fmt(duration)}</span>
      </div>
    </div>
  )
}
